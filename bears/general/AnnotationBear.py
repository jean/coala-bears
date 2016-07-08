from coalib.bearlib.languages.LanguageDefinition import LanguageDefinition
from coalib.bears.LocalBear import LocalBear
from coalib.results.HiddenResult import HiddenResult
from coalib.results.Result import Result, RESULT_SEVERITY
from coalib.results.SourceRange import SourceRange
from coalib.results.AbsolutePosition import AbsolutePosition


class AnnotationBear(LocalBear):
    AUTHORS = {'The coala developers'}
    AUTHORS_EMAILS = {'coala-devel@googlegroups.com'}
    LICENSE = 'AGPL-3.0'

    def run(self, filename, file, language: str, coalang_dir: str = None):
        """
        Finds out all the positions of strings and comments in a file.
        The Bear searches for valid comments and strings and yields their
        ranges as SourceRange objects in HiddenResults.

        :param language:        Language to be whose annotations are to be
                                searched.
        :param coalang_dir:     external directory for coalang file.
        :return:                HiddenResults containing a dictionary with
                                keys as 'strings' or 'comments' and values as
                                a tuple of SourceRanges of strings and
                                a tuple of SourceRanges of comments
                                respectively.
        """
        lang_dict = LanguageDefinition(language, coalang_dir=coalang_dir)
        single_strings = dict(lang_dict["string_delimiters"])
        multi_strings = dict(lang_dict["multiline_string_delimiters"])
        multi_comments = dict(lang_dict["multiline_comment_delimiters"])
        single_comments = dict(lang_dict["comment_delimiter"])
        strings = comments = ()
        try:
            strings, comments = self.find_annotation_ranges(file, filename,
                                                            single_strings,
                                                            multi_strings,
                                                            single_comments,
                                                            multi_comments)
        except NoCloseError as e:
            yield Result(self, str(e), severity=RESULT_SEVERITY.MAJOR,
                         affected_code=(e.code,))

        content = {"strings": strings, "comments": comments}
        yield HiddenResult(self, content)

    def find_annotation_ranges(self, file, filename,
                               single_strings, multi_strings,
                               single_comments, multi_comments):
        """
        find ranges of all annotations.

        :param file:
            A tuple of strings, with each string being a line in the file.
        :param filename:
            The name of the file.
        :param single_strings:
            A dictionary containing the various ways to  define single-line
            strings in a language.
        :param multi_strings:
            A dictionary contatining the various ways to define multi-line
            strings in a language.
        :param single_comments:
            A dictionary contatining the various ways to define single-line
            comments in a language.
        :param multi_comments:
            A dictionary contatining the various ways to define multi-line
            comments in a language.
        :return:
            Two tuples first contatining a tuple of strings, the second a tuple
            of comments.
        """
        text = ''.join(file)
        strings_range = []
        comments_range = []
        position = 0
        while position <= len(text):

            def get_new_position():
                for string in multi_strings.keys():
                    if text[position:].startswith(string):
                        _range, end_position = self.get_multiline(
                            file,
                            filename,
                            text,
                            string,
                            multi_strings[string],
                            position)
                        strings_range.append(_range)
                        return end_position + 1

                for string in single_strings.keys():
                    if text[position:].startswith(string):
                        strings = self.get_singleline_strings(
                            file, filename, text,
                            string, single_strings[string], position)
                        if strings:
                            _range, end_position = strings[0], strings[1]
                            strings_range.append(_range)
                            return end_position + 1

                for comment in multi_comments.keys():
                    if text[position:].startswith(comment):
                        _range, end_position = self.get_multiline(
                            file, filename, text,
                            comment, multi_comments[comment],
                            position)
                        comments_range.append(_range)
                        return end_position + 1

                for comment in single_comments.keys():
                    if text[position:].startswith(comment):
                        _range, end_position = self.get_singleline_comment(
                            file, filename, text, comment, position)
                        comments_range.append(_range)
                        return end_position + 1

                return position + 1

            position = get_new_position()

        return tuple(strings_range), tuple(comments_range)

    @staticmethod
    def get_multiline(file, filename,
                      text,
                      annotation_start,
                      annotation_end,
                      position):
        """
        Get sourcerange and end position of an annotation that can span
        multiple lines.

        :param file:
            A tuple of strings, with each string being a line in the file.
        :param filename:
            The name of the file.
        :param annotation_start:
            The string specifying the start of the annotation.
        :param annotation_end:
            The string specifying the end of the annotation.
        :param position:
            An integer identifying the position where the annotation started.
        :return:
            A SourceRange object holding the range of the multi-line annotation
            and the end_position of the annotation as an integer.
        """
        end_position = text.find(annotation_end,
                                 position + 1) + len(annotation_end) - 1
        if end_position == -1:
            _range = SourceRange.from_absolute_position(
                filename, AbsolutePosition(file, position))
            raise NoCloseError(annotation_start, _range)

        return SourceRange.from_absolute_position(
            filename,
            AbsolutePosition(file, position),
            AbsolutePosition(file, end_position)), end_position

    @staticmethod
    def get_singleline_strings(file, filename,
                               text,
                               string_start, string_end,
                               position):
        """
        Get sourcerange of a single-line string and its end position.

        :param file:
            A tuple of strings, with each string being a line in the file.
        :param filename:
            The name of the file.
        :param string_start:
            The string which specifies how a string starts.
        :param string_end:
            The string which specifies how a string ends.
        :position:
            An integer identifying the position where the string started.
        :return:
            A SourceRange object identifying the range of the single-line
            string and the end_position of the string as an integer.
        """
        end_position = text.find(string_end,
                                 position + 1) + len(string_end) - 1
        newline = text.find("\n", position + 1)
        if newline == -1:
            newline = len(text)
        if end_position == -1:
            _range = SourceRange.from_absolute_position(
                filename, AbsolutePosition(file, position))
            raise NoCloseError(string_start, _range)
        if newline > end_position:
            return SourceRange.from_absolute_position(
                filename,
                AbsolutePosition(file, position),
                AbsolutePosition(file, end_position)), end_position

    @staticmethod
    def get_singleline_comment(file, filename, text, comment, position):
        """
        :param file:
            A tuple of strings, with each string being a line in the file.
        :param filename:
            The name of the file.
        :param comment:
            The string which specifies the comment.
        :position:
            An integer identifying the position where the string started.
        :return:
            A SourceRange object identifying the range of the single-line
            comment and the end_position of the comment as an integer.
        """
        end_position = text.find("\n", position + 1)
        if end_position == -1:
            end_position = len(file) + 1
        return SourceRange.from_absolute_position(
            filename,
            AbsolutePosition(file, position),
            AbsolutePosition(file, end_position)), end_position


class NoCloseError(Exception):

    def __init__(self, annotation, code):
        Exception.__init__(self, annotation + " has no closure")
        self.code = code

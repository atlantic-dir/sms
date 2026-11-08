"""Exception types shared by all Font Sleuth modules."""


class FontSleuthError(Exception):
    """class:FontSleuthError--#58

    Purpose: Base class for every error whose message is safe to show to the user.
    Parameters: message, a plain-language sentence that says what went wrong and what to do next.
    Raises: nothing.
    Called from: every class that raises a user-facing error.
    Calls: Exception.
    """


class SourceError(FontSleuthError):
    """class:SourceError--#59

    Purpose: Signals that a file could not be opened or read (missing, corrupt, locked, unsupported).
    Parameters: message, a plain-language explanation.
    Raises: nothing.
    Called from: ImageSource.__init__ (#203), PdfSource.__init__ (#211), SourceFactory.open (#222).
    Calls: FontSleuthError.
    """


class AnalysisError(FontSleuthError):
    """class:AnalysisError--#60

    Purpose: Signals that the selected region cannot be analysed (no text, several lines, bad input).
    Parameters: message, a plain-language explanation.
    Raises: nothing.
    Called from: InkAnalyzer.analyze (#108), MaskBuilder.build (#227), FontMatcher.rank (#100), AnalysisService.analyze (#5).
    Calls: FontSleuthError.
    """


class CancelledError(FontSleuthError):
    """class:CancelledError--#61

    Purpose: Signals that the user cancelled a long-running job.
    Parameters: message, a short explanation.
    Raises: nothing.
    Called from: FontMatcher.rank (#100), FontScanner.scan (#85).
    Calls: FontSleuthError.
    """


class MissingTextError(AnalysisError):
    """class:MissingTextError--#62

    Purpose: Signals that the picture needs the user to type the text it shows before fonts can be matched.
    Parameters: message, a plain-language explanation.
    Raises: nothing.
    Called from: AnalysisService.analyze_pixels (#6), MainWindow._on_job_failed (#135).
    Calls: AnalysisError.
    """

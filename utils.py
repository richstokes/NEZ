DEBUG_MODE = False  # Default to quiet; enable via set_debug(True) when needed


def set_debug(value):
    """
    Set debug mode on/off

    Args:
        value (bool): True to enable debugging, False to disable
    """
    global DEBUG_MODE
    DEBUG_MODE = value


def debug_print(text):
    """
    Prints the given text to the console for debugging purposes.

    Args:
        text (str): The text to print.
    """
    if DEBUG_MODE:
        print(text)

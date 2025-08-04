DEBUG_MODE = True


def debug_print(text):
    """
    Prints the given text to the console for debugging purposes.

    Args:
        text (str): The text to print.
    """
    if DEBUG_MODE:
        print(text)

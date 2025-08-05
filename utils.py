DEBUG_MODE = True  # Enable debug output to see what's happening


def debug_print(text):
    """
    Prints the given text to the console for debugging purposes.

    Args:
        text (str): The text to print.
    """
    if DEBUG_MODE:
        print(text)

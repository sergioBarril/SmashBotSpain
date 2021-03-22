import unicodedata

def no_accents(text):
    text = unicodedata.normalize('NFD', text)\
        .encode('ascii', 'ignore')\
        .decode("utf-8")
    return str(text)

def key_format(text):
    return no_accents(text.lower()) if text else ""

def list_with_and(elements, bold=False, italics=False):
    """
    Returns a string with all elements joined by ',' except the last one
    which is joined with an "and" ("y" in spanish).
    """    
    style = ""
    if bold:
        style += "**"
    if italics:
        style += "_"
    
    if not elements:
        return ""
    elif len(elements) == 1:
        return f"{elements[0]}"
    else:        
        text = ", ".join(elements[:-1])
        text += f"{style} y {style}"
        text += elements[-1]
        return text
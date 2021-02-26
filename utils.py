from os import unlink

def unlink_safe(path):
    try:
        unlink(path)
        return True
    except:
        return False
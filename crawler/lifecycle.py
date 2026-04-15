from seleniumbase import BaseCase
import shutil
from pathlib import Path

def copy_profile(src_dir: Path, dest_dir: Path):
    """
    Copy Chrome profile. This creates a temporary
    profile for each runtime to use.
    Doing so, we avoid our profile size growing
    indefinitely as we crawl more and more websites.

    Call this method before initializing the browser.
    Usage:
    sb_profile = Path(__file__).parent.parent / "sb_profile"
    tmp_profile = Path("/tmp/chrome_profile")
    copy_profile(sb_profile, tmp_profile)
    """
    if dest_dir.exists():
        shutil.rmtree(dest_dir)

    def ignore_singleton(path, names):
        # Chrome singleton is for runtime sockets and can't be copied.
        ignored = []
        for name in names:
            if name.startswith("Singleton"):
                ignored.append(name)
        return ignored
    
    shutil.copytree(src_dir, dest_dir, ignore=ignore_singleton)


def clear_tabs(sb: BaseCase):
    """
    Clear all tabs except the first one.
    Call this method after each crawl or 
    a set amount of crawls.
    Ensures a clean state and we're not wasting memory.
    """
    tabs = sb.driver.window_handles
    while len(tabs) > 1:
        sb.driver.switch_to.window(tabs[-1])
        sb.driver.close()
        tabs = sb.driver.window_handles
    sb.driver.switch_to.window(tabs[0])


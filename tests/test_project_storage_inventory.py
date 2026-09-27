import os
from scripts.inventory_project_storage import inventory


def test_inventory_counts_hardlinks_once_and_does_not_follow_symlink(tmp_path):
    (tmp_path/'a').mkdir(); (tmp_path/'b').mkdir()
    (tmp_path/'a'/'data.json').write_bytes(b'12345')
    os.link(tmp_path/'a'/'data.json',tmp_path/'b'/'copy.json')
    (tmp_path/'empty').write_bytes(b'')
    (tmp_path/'link').symlink_to(tmp_path, target_is_directory=True)
    report=inventory(tmp_path)
    assert report['totals']['files']==3
    assert report['totals']['directories']==2
    assert report['totals']['unique_files']==2
    assert report['totals']['logical_bytes']==10
    assert report['totals']['unique_logical_bytes']==5
    assert report['totals']['symlinks_not_followed']==1
    assert report['totals']['hardlink_aliases']==1
    assert report['errors']==[]

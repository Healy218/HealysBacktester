# V6 historical input archive

Original: `nn_meta/expanded_inputs/v6-local-20260906`

Each tar.zst contains repo-relative paths, Unix metadata, ACLs and xattrs. Extract onto a Linux filesystem, not directly as loose files on exFAT.

From the repository root, for each archive run:

    tar --same-permissions --xattrs --acls -I zstd -xf /path/to/archive.tar.zst

Extract context-and-stores.tar.zst last to restore parent metadata. Verify every compressed SHA256 against its corresponding verified.json before restoration. All archives passed full GNU tar source comparisons before source retirement. restore-smoke.json records a real extraction and hash comparison. These are historical V6 inputs, not newly admitted V7 data.

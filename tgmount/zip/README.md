
## Details

sadly files seeking inside a zip works by reading the offset bytes so it's slow
https://github.com/python/cpython/blob/main/Lib/zipfile.py#L1116

also id3v1 tags are stored in the end of a file :)
https://github.com/quodlibet/mutagen/blob/master/mutagen/id3/_id3v1.py#L34

and most of the players try to read it. So just adding an mp3 or flac
to a player will fetch the whole file from the archive

setting `fix_Id3v1` will patch read function so it returns 4096 zero bytes when
1. less than `max_total_read = 128KB` bytes has been read from the file so far
2. file_size - offset < `distance_to_file_end = 16KB`
3. size = 4096 (usually players read this amount looking for id3v1 (requires further
investigation to find a less hacky way))

## Greenback


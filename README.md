# Overview

Creates virtual file system with files posted on telegram.  
<!-- tgmount lets you to mount files uploaded to telegram as a virtual file system 
so access them like regular files from a cloud without downloading. This allows to use
regular desktop media players to listen to music streaming it directly from telegram servers. Pictures and videos 

Features:
* Flexible VFS structure configuration 
* ZIP archives as folders
* Multiple files organization strategies
-->

**VERY ALPHA SO FAR**

Table of Contents
=================
* [Installation](#installation)
* [Requirements](#requirements)
* [Basic usage](#requirements)
* [Mounting multiple entities](#mounting-multiple-entities)
  * [Sample config](#sample-config)
* [Client commands](#client-commands)
  * [mount](#tgmount-mount)
  * [mount config](#tgmount-mount-config)
  * [list dialogs](#tgmount-list-dialogs)
  * [list documents](#tgmount-list-documents)
  * [download](#tgmount-download)
* [Config file structure](#config-file-structure)
* [Playing flac and mp3 from a zip archive](#playing-flac-and-mp3-from-a-zip-archive)
* [Known bugs](#known-bugs)

## Requirements
- Linux
- Python?

## Installation:

```
pip install tgmount
```

## Basic usage

To obtain your API id follow [official manual](https://core.telegram.org/api/obtaining_api_id).  Running the program for the first time will require authentication.

```
$ export TGAPP=1234567:deadbeef0d04a3efe93e1af778773d6f0 TGSESSION=tgfs
```

To mount a channel/chat/group

```
cli.py mount tgmounttestingchannel ~/mnt/tgmount1/
```

To mount an entity that doesn't have a username you will need to get its id. 
```bash
cli.py list dialogs | grep 'my friends private chat'
```

To mount zip files as directories use `UnpackedZip` producer

```
cli.py mount tgmounttestingchannel ~/mnt/tgmount1/ --producer UnpackedZip
```

Use config file to create a more complex vfs structure  

```
cli.py mount tgmounttestingchannel ~/mnt/tgmount1/ --root-config examples/root_config.yaml
```


## Mounting multiple entities

To mount multiple entities use `mount-config` command

```
cli.py mount-config examples/config.yaml
```

### Sample config
```yaml
# can be overwritten by --mount-dir argument
mount_dir: /home/horn/mnt/tgmount1

client:
  session: tgfs
  api_id: 123
  api_hash: deadbeed121212121

# 
message_sources:

  ru2chmu:
    entity: ru2chmu
    updates: False
    limit: 1000

  friends:
    entity: -388004022
    limit: 1000
    
caches:
  memory1:
    type: memory
    capacity: 300MB
    block_size: 128KB

root:
  muzach:
    # A document will not be mounted more than once when it appears in a 
    # different messages. `recursive` means this filter will also be applied 
    # down the folders tree
    filter: { filter: OnlyUniqueDocs, recursive: True }
    # Messages from `ru2chmu` will be used to produce content in the nested folders
    source: { source: ru2chmu, recursive: True }
    # creates subfolder named `music`
    music:
      filter: 
        # the directory will contain music and zip archives
        Union: [MessageWithMusic, MessageWithZip]
      # zip archives will be mounted as folders
      producer: UnpackedZip
      # using cache speeds up reading from the archives
      cache: memory1
    texts:
      # messages with text 
      filter: MessageWithText
      # this commands tgmount to treat messages with both document and text
      # as text files
      treat_as: MessageWithText

  friends:
    source: {source: friends, recursive: True}
    music-by-senders:
      producer:
        # this producer creates a separate directory for every sender in the entity
        BySender:
          dir_structure:
            # these directories will only contain music 
            filter: MessageWithMusic
    liked-music:
      # this directory will be containing all music with thumb up reaction
      filter: 
        And: 
          - MessageWithMusic
          - ByReaction: 
              reaction: 👍
    images:
      filter: 
        Union: [MessageWithCompressedPhoto, MessageWithDocumentImage]
```

More about config structure read in [Config file structure](#config-file-structure)

## Client commands

<!-- `tgmount auth` -->

### tgmount mount

```
cli.py mount [--filter FILTER] [--root-config ROOT_CONFIG]
[--producer PRODUCER] [--offset-date OFFSET_DATE] [--offset-id OFFSET_ID] 
[--max-id MAX_ID] [--min-id MIN_ID] [--wait_time WAIT_TIME] [--limit LIMIT] 
[--reply-to REPLY_TO] [--from-user FROM_USER] [--reverse] [--mount-texts] [--no-updates] 
[--debug-fuse] [--min-tasks MIN_TASKS] entity mount-dir
```

Define the structure of the mounted folder by one of these options
```
--producer PRODUCER
--root-config ROOT_CONFIG
```

Available producers:

```python
PlainDir    # just a list of files (default)
UnpackedZip # PlainDir but zips are mounted as folders
BySender    # files grouped in folders by sender
ByForward   # forwarded files grouped by source entity
ByPerformer # music grouped by performers
ByReactions # files grouped by reaction
```

The following arguments work as described in [TelegramClient.get_messages](https://docs.telethon.dev/en/stable/modules/client.html#telethon.client.messages.MessageMethods.get_messages). 

```
--filter [FILTER]
--offset-date OFFSET_DATE
--offset-id OFFSET_ID
--max-id MAX_ID
--min-id MIN_ID
--wait_time WAIT_TIME
--limit LIMIT
--reply-to REPLY_TO
--from-user FROM_USER
--reverse
```


Available [telegram filters](https://core.telegram.org/type/MessagesFilter):

```python
InputMessagesFilterDocument
InputMessagesFilterPhotos
InputMessagesFilterVideo
InputMessagesFilterPhotoVideo
InputMessagesFilterUrl
InputMessagesFilterGif
InputMessagesFilterVoice
InputMessagesFilterMusic
InputMessagesFilterRoundVoice
InputMessagesFilterRoundVideo
InputMessagesFilterMyMentions
```

Using these filter speeds up fetching process but these filter cannot be composed.

If you don't need updates 
```
--no-updates
```

If you want to also to mount text messages as text files

```
--mount-texts
```

Other arguments
```
--debug-fuse
--min-tasks MIN_TASKS
```

### tgmount mount-config

```
cli.py mount-config [--mount-dir MOUNT_DIR] CONFIG_FILE MOUNT_DIR
```

### tgmount list dialogs

```
cli.py list dialogs
```

### tgmount list documents

```
cli.py list documents [--filter FILTER] [--offset-date OFFSET_DATE] [--offset-id OFFSET_ID]
[--max-id MAX_ID] [--min-id MIN_ID] [--wait_time WAIT_TIME] [--limit LIMIT] 
[--reply-to REPLY_TO] [--from-user FROM_USER] [--reverse] [--json]
[--print-message] [--include-unsupported] [--only-unsupported] [--all-types]
[--only-unique-docs] entity
```

```--print-message```

Include stringified message object in the output

`--all-types`

Print all classes a message matches

`--only-unique-docs`

Exclude repeating documents 

`--include-unsupported`

Include messages that are not supported for mounting

`--only-unique-docs`

Print only them

`--json`

Print in json format

### tgmount download

```
tgmount download [--output-dir OUTPUT_DIR] [--keep-filename] [--request_size REQUEST_SIZE] entity ids [ids ...]
```

`--keep-filename`

Keep original filenames

`--output-dir`

Destination folder for files

`--request_size`

How much data to fetch per request

`entity`

Entity to download from

`ids`

Messages ids

Example:

```
cli.py download -O /tmp -R 256KB tgmounttestingchannel 532 11 51 18 
```

Im combination with `list documents`

```bash
cli.py download ru_python $(cli.py list documents ru_python --filter InputMessagesFilterDocument --limit 10 --json | jq  '.[]|.id') -O /tmp
```


## Config file structure

Config file has the following sections: 
- `client`
- `message_sources`
- `caches`
- `root`

`caches` section is optional.

### Top level properties
```yaml
# optional. can be overwritten by --mount-dir argument 
mount_dir: ~/mnt/tgmount
```
### client

Contains settings for the telegram client

```yaml
client:
  # telethon session name 
  session: session_name

  # telegram api credentials
  api_id: int
  api_hash: str

  # optional field
  request_size: 128KB
```

### message_sources
A message source defines a list of messages that will be used in vfs tree construction. Every message source is a separate [TelegramClient.get_messages](https://docs.telethon.dev/en/stable/modules/client.html#telethon.client.messages.MessageMethods.get_messages) request. Message source is also subscribed to events of posting, removing and editing messages in the entity it is sourced from. 

```yaml
message_sources:
  # key defines id of the message source to reference in the `root` section 
  source1: 
    # channel/group/chat id to fetch messages from
    # string or int
    entity: tgmounttestingchannel
    
    # all the following fields are optional

    # whether to listen for updates. Default: true
    updates: True

    # Filter for message types. If not set all the messages types including text 
    # messages will be fetched
    filter: MessageWithMusic

    # limits the number of messages
    limit: 1000

    # format is `31/12/2023` or '31/12/2023 13:00'
    offset_date: `31/12/2023`

    offset_id: 0
    min_id: 0
    max_id: 0
    wait_time: None
    reply_to: int
    from_user: str | int
    reverse: False
```

### caches

Defines cache storages for documents. Cached parts of a document will not be fetched twice. Usually this is not needed because OS file system does caching by itself. Cache is needed in couple with `UnpackedZip` producer since the OS file system cache is not applied in case of using this producer.

```yaml
caches:
  # the key defines cache id to be referenced in `root` section
  cache1:
    # currently only memory cache is supported 
    type: memory
    # The size of the cache
    capacity: 300MB
    # optional block size, default: 128KB
    block_size: 256KB
```

### root

This section defines the structure of the mounted folder.

```yaml
root:
  # optional. sets the message source for the current directory. If this is not
  # set and there is no recursive filter has been defined before, the folder 
  # will not contain any files
  source: source1
  source: {source: source1}

  # sets the message source for the current and for nested folders
  source: {source: source1, recursive: True}
  
  # optional. sets a filter for the current folder. Default is no filter
  filter: MessageWithMusic
  filter: {filter: MessageWithMusic}

  # sets a filter for the current folder and subfolders
  filter: {filter: MessageWithMusic, recursive: True}

  # sets a filter for the current folder and subfolders overwriting another recursive filter if any 
  filter: {filter: MessageWithMusic, overwright: True, recursive: True}

  # the following combines multiple filters. Only messages that match every filter
  # in the list will pass. The filter below allows all documents that
  # that are not video, photo or audio and not a zip file 
  filter: 
    - MessageWithOtherDocument
    - Not:
      - ByExtension: .zip

  # on line
  filter: {filter: [MessageWithOtherDocument, Not: {ByExtension: .zip}], overwright: True, recursive: True}

  # defines a producer that controls the content of the folder. 
  # Default is PlainDir
  producer: BySender

  # producer may have properties
  producer: 
    BySender:
      dir_structure:
        music: 
          filter: MessageWithMusic
        voices: 
          filter: MessageWithVoice
      use_get_sender: true

  # sets a cache for the current folder
  # referencing a cache defined in `caches` folder 
  cache: memory1

  # dynamically creates a cache to use in this folder
  cache: 
    type: memory
    capacity: 300MB

  # optional. wrapper that modifies the resulting content of the folder 
  wrapper: ExcludeEmptyDirs

  # optional. Defines the priority of how to classify a message if multiple classes
  # match its type. E.g. a message with both a document and a text message  
  treat_as: MessageWithText

  # to define subfolders
  documents:
    # 'documents' folder will only contain the two following subfolders 
    docs_from_source1:
      source: source1
      filter: MessageWithDocument
    docs_from_source2:  
      source: source2
      filter: MessageWithDocument
```


#### source

Message source is a list of messages which is used to produce a directory content. Message source is initialized from get_messages() request and is updated by events of posting message, removing message and editing message in the corresponding entity. 

Producer is subscribed to a message source and takes a care of the directory it is responsible for. It manages it by adding and removing files and subfolders.

The content of a folder is defined by a combination of properties `source`, `filter`, `producer` and `treat_as`. 

This will create a tree of empty folders
```yaml
root:
  everything:
  photos:
  texts:
  round-and-voice:
    rounds:
    voices:
```
The config will result into
```
/everything
/photos
/texts
/round-and-voice
/round-and-voice/rounds
/round-and-voice/voices
```
To fill the directories with files we need to specify a source for every folder that is supposed to contain files
```yaml
root:
  everything:
    source: source1 
  photos:
    source: source1
  texts:
    source: source1
  round-and-voice:
    rounds:
      source: source1
    voices:
      source: source1
```

In result every directory that has `source` property will contain all the files from the specified source.

Let's add filters 

```yaml
root:
  everything:
    # don't need filter here
    source: source1
  photos:
    source: source1
    filter: MessageWithCompressedPhoto
  texts:
    source: source1
    filter: MessageWithText
    treats_as: MessageWithText
  round-and-voice:
    rounds:
      source: source1
      filter: MessageWithKruzhochek
    voices:
      source: source1
      filter: MessageWithVoice
```
As soon as the only source used in the structure is "source1" we can get rid of repeating it by using `recursive` property of `source`.

```yaml
root:
  source: {source: source1, recursive: True}
  everything:
    filter: All
  photos:
    filter: MessageWithCompressedPhoto
  texts:
    filter: MessageWithText
    treats_as: MessageWithText
  round-and-voice:
    rounds:
      filter: MessageWithKruzhochek
    voices:
      filter: MessageWithVoice
```

Note that
1. The root itself will not contain any files because source with `recursive` flag doesn't trigger file producing
2. We had to specify `filter` in "everything" to trigger file producer. For the same effect we could have specified a producer instead.
```yaml
everything:
  # triggers producing from the recursive source
  producer: PlainDir
```  

The complete rules:

A folder will be produced with content from a message source in cases when:
1. source is specified and it's not recursive
2. recursive source is in the context and `filter` property specified and it's not recursive
3. recursive source is in the context and `producer` prop is specified

#### filter

By message type:

```python
MessageWithDocument # Message with a document attached (message with compressed
#  image doesn't match) 
MessageWithCompressedPhoto # with a compressed image (photo)
MessageDownloadable # `MessageWithDocument` or `MessageWithCompressedPhoto`
MessageWithAnimated # stickers, gifs
MessageWithAudio # voices and music
MessageWithVoice # voice
MessageWithKruzhochek # round video
MessageWithDocumentImage # uncompressed image
MessageWithFilename # document with a filename attribute
MessageWithMusic # music
MessageWithVideo # round video, video documents, stickers, gifs
MessageWithVideoFile # video documents
MessageWithSticker # sticker
MessageWithOtherDocument # Any document that doesn't fall in the previous categories
MessageWithZip # zip file
MessageWithText # message with text message
MessageWithoutDocument # message with no document and no photo
MessageWithReactions # message with reactions
MessageForwarded # forwarded message

# Telegram filters
InputMessagesFilterPhotos     # MessageWithCompressedPhoto
InputMessagesFilterVideo      # MessageWithVideo
InputMessagesFilterPhotoVideo # MessageWithCompressedPhoto | MessageWithVideo
InputMessagesFilterDocument   # MessageWithOtherDocument | MessageWithDocumentImage
InputMessagesFilterGif        # MessageWithAnimated
InputMessagesFilterVoice      # MessageWithVoice
InputMessagesFilterMusic      # MessageWithMusic
InputMessagesFilterRoundVideo # MessageWithKruzhochek
InputMessagesFilterRoundVoice # MessageWithKruzhochek | MessageWithVoice
```

Other filters

```yaml
# Filter wrapper to reverse a filter. 
Not: MessageWithReactions

# Combines multiple filters. If any matches
Union: 
  - MessageWithDocumentImage
  - MessageWithCompressedPhoto

# Combines multiple filters. If every matches
And:
  - MessageForwarded
  - MessageWithVideo

# same as
filter: [MessageForwarded, MessageWithVideo]

# takes first `count` messages
First:
  count: 10

# takes last `count` messages
Last:
  count: 10

# Filter by a filename extension
ByExtension: .zip

# will only leave unique docs
OnlyUniqueDocs:
  # optional. Control which document, first appeared or last appeared, will stay.
  # default: first
  picker: last 
  picker: first 

# passthrough filter. Used to trigger tgmount to produce content in the folder
# or to reset recursive filter
All

# sequentially filters messages. E.g. last 10 unique documents 
Seq:
  - MessageWithDocument
  - OnlyUniqueDocs
  - Last: 10

# matches reactions
ByReaction:
  reaction: 👍
  # optional. default: 1
  minimum: 5
```

#### producer

```python
PlainDir
BySender
ByForward
ByPerformer
ByReactions
SysInfo
UnpackedZip
```

## Playing flac and mp3 from a zip archive
1. Seeking in files which are stored in a zip archive only works by reading the 
offset bytes.  
2. id3v1 tags are stored in the end of a media file :)
https://github.com/quodlibet/mutagen/blob/master/mutagen/id3/_id3v1.py#L34

And most of the players try to read it. So just adding a mp3 or flac
to a player will fetch the whole file from the telegram cloud.

In current moment this is solved by custom read function for mp3 and flac files 
in archives. The `read` call returns 4096 zero bytes when
  1. less than `max_total_read = 128KB` bytes has been read from the file so far
  2. `file_size - offset < distance_to_file_end = 16KB`
  3. `size == 4096` (usually players read this amount looking for id3v1 (requires 
  further investigation to find a less hacky way))

  See `FileContentZipFixingId3v1` class

To disable this behavior use `--no-fix-id3v1` argument with `mount` command. 
In case of mounting a config set `fix_id3v1` property of `UnpackedZip` to False:
```yaml
producer: {UnpackedZip: {fix_id3v1: False}}
```

## Known bugs
- No updates received during reconnection
- Combination of `--filter`, `--offset-date` and `--reverse` always returns empty result
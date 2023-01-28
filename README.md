# Overview

New version of tgmount


## Requirements
- Linux
- Python?


## Installation:

```
virtualenv .venv3.10 -p python3.10
source .venv3.10/bin/activate
pip install -r requirements.txt
python cli.py list dialogs
```

## Basic usage

To obtain your API id follow [official manual](https://core.telegram.org/api/obtaining_api_id).  Running the program for the first time will require authentication.

```
$ export TGAPP=1234567:deadbeef0d04a3efe93e1af778773d6f0
```

To mount a channel 

```
cli.py mount tgmounttestingchannel ~/mnt/tgmount1/ --filter InputMessagesFilterDocument
```

Without text files
```
cli.py mount tgmounttestingchannel ~/mnt/tgmount1/ --filter InputMessagesFilterDocument
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

## Client

<!-- `tgmount auth` -->

`tgmount mount`

`tgmount mount-config`

<!-- `tgmount list` -->

`tgmount list dialogs`

`tgmount list documents`

<!-- `tgmount download` -->



## Config file structure

To mount multiple entities use `mount-config` command

```
cli.py mount-config examples/config.yaml ~/mnt/tgmount1/
```


Sample config:
```yaml
mount_dir: /home/horn/mnt/tgmount1

client:
  session: tgfs
  api_id: 123
  api_hash: deadbeed121212121

message_sources:
  
  ru2chmu:
    entity: ru2chmu
    filter: InputMessagesFilterDocument
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
    source: {source: ru2chmu, recursive: True}
    music:
      filter: 
        # the directory will contain music and zip archives
        Union: [MessageWithMusic, MessageWithZip]
      # zip archives will be mounted as folders
      producer: UnpackedZip
      # using cache speeds up reading from the archives
      cache: memory1
    texts:
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
            # these directories will only contain 
            filter: MessageWithMusic
    liked-music:
      # this directory will be containing all music with thumb up reaction
      filter: 
        And: 
          - MessageWithMusic
          - ByReaction: 
              reaction: 👍
    texts:
      filter: MessageWithText
      # this commands tgmount to treat file with both document and text
      # as text messages
      treat_as: MessageWithText
```

### Message source 

Every message source is a separate [get_messages]((https://docs.telethon.dev/en/stable/modules/client.html#telethon.client.messages.MessageMethods.get_messages)
) request. 


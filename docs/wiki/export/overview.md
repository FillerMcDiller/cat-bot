## Overview

When a cat is caught, the bot randomly picks a new time according to the channel's timing settings. The bot saves this target time to the database and creates a task which waits until that time hits to spawn another cat.

It will choose the default if there is no custom spawn message.

## Spawn and Caught Messages

The default spawn message looks like this:

```
{emoji} {type} cat has appeared! Type "cat" to catch it!
```

The default catch message looks like this for most cats:

```
{username} cought {emoji} {type} cat!!!!1!

You now have {number} cats of dat type!!!

this fella was cought in {time}!!!!
```

For special catch messages (by default), please refer to Cat Types.

## Rains

Starting a rain pauses the normal spawn cycle and forcibly spawns cats randomly every ~2.5-3 seconds.

There is a set amount of cats spawned in each rain, calculated as rain duration in seconds / 2.75.

## Restarts

When Cat Bot finishes starting up, it goes through every channel in which the target time is in and spawns a cat in them. This covers spawns which should have occurred during the restart. Additionally, every 5 minutes, a loop is run to check for any channels which are past due.

## Commands

/setup bootstraps the spawn loop for a channel.

/forcespawn forces a cat to spawn immediately.

Spawn and catching messages can be modified with the /changemessage command.

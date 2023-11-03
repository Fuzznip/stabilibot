def is_channel(channel1: str, channel2: str) -> bool:
  return channel1.casefold() == channel2.casefold()

def is_message_in_channel(message, channel: str) -> bool:
  return hasattr(message, "channel") and hasattr(message.channel, "name") and is_channel(message.channel.name, channel)

def is_message_in_channels(message, channels: list[str]) -> bool:
  for channel in channels:
    if is_message_in_channel(message, channel):
      return True
    
  return False

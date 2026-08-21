#!/usr/bin/env python3
from pathlib import Path

PATH = Path("TShockAPI/GetDataHandlers.cs")
text = PATH.read_text(encoding="utf-8-sig")


def braced_end(src: str, brace: int) -> int:
    depth = 0
    in_string = False
    verbatim = False
    escape = False
    i = brace
    while i < len(src):
        c = src[i]
        if in_string:
            if verbatim:
                if c == '"' and i + 1 < len(src) and src[i + 1] == '"':
                    i += 2
                    continue
                if c == '"':
                    in_string = False
                    verbatim = False
            else:
                if escape:
                    escape = False
                elif c == '\\':
                    escape = True
                elif c == '"':
                    in_string = False
        else:
            if c == '@' and i + 1 < len(src) and src[i + 1] == '"':
                in_string = True
                verbatim = True
                i += 2
                continue
            if c == '"':
                in_string = True
            elif c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return i + 1
        i += 1
    raise RuntimeError("unbalanced braces")


def method_span(src: str, name: str):
    needle = f"\t\tprivate static bool {name}("
    start = src.index(needle)
    brace = src.index('{', start)
    end = braced_end(src, brace)
    # Include trailing blank line to keep formatting stable.
    while end < len(src) and src[end] in '\r\n':
        end += 1
    return start, end


def patch_method(name: str, old: str, new: str):
    global text
    start, end = method_span(text, name)
    body = text[start:end]
    count = body.count(old)
    if count != 1:
        raise RuntimeError(f"{name}: expected one occurrence of {old!r}, got {count}")
    body = body.replace(old, new, 1)
    text = text[:start] + body + text[end:]


def remove_method(name: str):
    global text
    start, end = method_span(text, name)
    text = text[:start] + text[end:]


def remove_registration(line: str):
    global text
    count = text.count(line)
    if count != 1:
        raise RuntimeError(f"expected one registration {line!r}, got {count}")
    text = text.replace(line, "", 1)


# 1.4.5.7 no longer accepts these as client->server packets. Packet 22 is
# server->client-only; 126 is server->client-only; 145/148 are deprecated and
# have no MessageBuffer cases at all.
for registration in (
    "\t\t\t\t\t{ PacketTypes.ItemOwner, HandleItemOwner },\n",
    "\t\t\t\t\t{ PacketTypes.SyncRevengeMarker, HandleSyncRevengeMarker },\n",
    "\t\t\t\t\t{ PacketTypes.SyncItemsWithShimmer, HandleItemDrop },\n",
    "\t\t\t\t\t{ PacketTypes.SyncItemCannotBeTakenByEnemies, HandleItemDrop },\n",
):
    remove_registration(registration)

remove_method("HandleItemOwner")
remove_method("HandleSyncRevengeMarker")

# Match vanilla's server-side identity canonicalization before TShock exposes
# parsed IDs to plugin hooks. The client byte is still consumed to preserve the
# packet layout, but it is never trusted as the sender identity.
canon = "args.Data.ReadInt8(); // Vanilla replaces the client-supplied player id with whoAmI on the server.\n\t\t\t"
patch_method("HandlePlayerInfo", "byte playerid = args.Data.ReadInt8();", canon + "byte playerid = (byte)args.Player.Index;")
patch_method("HandlePlayerSlot", "byte plr = args.Data.ReadInt8();", canon + "byte plr = (byte)args.Player.Index;")
patch_method("HandleSpawn", "byte player = args.Data.ReadInt8();", canon + "byte player = (byte)args.Player.Index;")
patch_method("HandlePlayerUpdate", "byte playerID = args.Data.ReadInt8();", canon + "byte playerID = (byte)args.Player.Index;")
patch_method("HandlePlayerHp", "var plr = args.Data.ReadInt8();", canon + "var plr = (byte)args.Player.Index;")
patch_method("HandleTogglePvp", "byte id = args.Data.ReadInt8();", canon + "byte id = (byte)args.Player.Index;")
patch_method("HandlePlayerZone", "var plr = args.Data.ReadInt8();", canon + "var plr = (byte)args.Player.Index;")
patch_method("HandleNpcTalk", "var plr = args.Data.ReadInt8();", canon + "var plr = (byte)args.Player.Index;")
patch_method("HandlePlayerMana", "var plr = args.Data.ReadInt8();", canon + "var plr = (byte)args.Player.Index;")
patch_method("HandlePlayerTeam", "byte id = args.Data.ReadInt8();", canon + "byte id = (byte)args.Player.Index;")
patch_method("HandlePlayerBuffList", "var id = args.Data.ReadInt8();", canon + "var id = (byte)args.Player.Index;")
patch_method("HandleSpecial", "var id = args.Data.ReadInt8();", canon + "var id = (byte)args.Player.Index;")
patch_method("HandlePlayerKillMeV2", "var id = args.Data.ReadInt8();", canon + "var id = (byte)args.Player.Index;")
patch_method("HandleEmoji", "byte playerIndex = args.Data.ReadInt8();", canon + "byte playerIndex = (byte)args.Player.Index;")
patch_method("HandleTileEntityDisplayDollItemSync", "byte playerIndex = args.Data.ReadInt8();", canon + "byte playerIndex = (byte)args.Player.Index;")
patch_method("HandleRequestTileEntityInteraction", "byte playerIndex = args.Data.ReadInt8();", canon + "byte playerIndex = (byte)args.Player.Index;")
patch_method("HandleSyncTilePicking", "byte playerIndex = args.Data.ReadInt8();", canon + "byte playerIndex = (byte)args.Player.Index;")
patch_method("HandleSyncLoadout", "var playerIndex = args.Data.ReadInt8();", canon + "var playerIndex = (byte)args.Player.Index;")

# Guard a pre-existing out-of-bounds access: the old code indexed Main.tile
# before checking the packet coordinates.
patch_method(
    "HandleDoorUse",
    "\t\t\tushort tileType = Main.tile[x, y].type;\n\n\t\t\tif (x >= Main.maxTilesX || y >= Main.maxTilesY || x < 0 || y < 0) // Check for out of range\n",
    "\t\t\tif (x >= Main.maxTilesX || y >= Main.maxTilesY || x < 0 || y < 0) // Check for out of range\n",
)
patch_method(
    "HandleDoorUse",
    "\t\t\t\treturn true;\n\t\t\t}\n\n\t\t\tif (action < 0 || action > 5)",
    "\t\t\t\treturn true;\n\t\t\t}\n\n\t\t\tushort tileType = Main.tile[x, y].type;\n\n\t\t\tif (action < 0 || action > 5)",
)

# Vanilla rejects invalid NPC slots before indexing Main.npc. TShock previously
# indexed Main.npc[id] in its permission-rejection path first.
patch_method(
    "HandleUpdateNPCHome",
    "\t\t\tvar householdStatus = args.Data.ReadInt8();\n\n\t\t\tif (OnUpdateNPCHome",
    "\t\t\tvar householdStatus = args.Data.ReadInt8();\n\n\t\t\tif (id < 0 || id >= Main.maxNPCs)\n\t\t\t{\n\t\t\t\tTShock.Log.ConsoleDebug(GetString(\"GetDataHandlers / HandleUpdateNPCHome rejected invalid NPC index {0} from {1}\", id, args.Player.Name));\n\t\t\t\treturn true;\n\t\t\t}\n\n\t\t\tif (OnUpdateNPCHome",
)

# Vanilla's team packet indexes Main.teamColor directly. Consume malformed team
# values in TShock instead of allowing crafted packets to reach that access.
patch_method(
    "HandlePlayerTeam",
    "\t\t\tbyte team = args.Data.ReadInt8();\n\t\t\tif (OnPlayerTeam",
    "\t\t\tbyte team = args.Data.ReadInt8();\n\t\t\tif (team >= Main.teamColor.Length)\n\t\t\t{\n\t\t\t\tTShock.Log.ConsoleDebug(GetString(\"GetDataHandlers / HandlePlayerTeam rejected invalid team {0} from {1}\", team, args.Player.Name));\n\t\t\t\treturn true;\n\t\t\t}\n\n\t\t\tif (OnPlayerTeam",
)

# TEDisplayDoll.ReadItem consumes the item payload and then ignores an invalid
# slot. TShock used to index items[slot] before any bounds check.
patch_method(
    "HandleTileEntityDisplayDollItemSync",
    "\t\t\t\tItem oldItem = items[slot];\n\n\t\t\t\tushort itemType = args.Data.ReadUInt16();\n\t\t\t\tushort stack = args.Data.ReadUInt16();\n\t\t\t\tint prefix = args.Data.ReadByte();\n",
    "\t\t\t\tushort itemType = args.Data.ReadUInt16();\n\t\t\t\tushort stack = args.Data.ReadUInt16();\n\t\t\t\tint prefix = args.Data.ReadByte();\n\n\t\t\t\tif ((uint)slot >= (uint)items.Length)\n\t\t\t\t{\n\t\t\t\t\tTShock.Log.ConsoleDebug(GetString(\"GetDataHandlers / HandleTileEntityDisplayDollItemSync rejected invalid slot {0} from {1}\", slot, args.Player.Name));\n\t\t\t\t\treturn true;\n\t\t\t\t}\n\n\t\t\t\tItem oldItem = items[slot];\n",
)

PATH.write_text(text, encoding="utf-8-sig")
print("Applied Terraria 1.4.5.7 packet handler audit fixes.")

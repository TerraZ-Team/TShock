import re
from pathlib import Path


def replace_method(text, name, next_name, replacement):
    pattern = rf'\t\tprivate static bool {name}\(GetDataHandlerArgs args\)\n\t\t\{{.*?(?=\n\t\tprivate static bool {next_name}\(GetDataHandlerArgs args\))'
    text, count = re.subn(pattern, replacement.rstrip(), text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f'Could not replace {name}: {count} matches')
    return text


path = Path('TShockAPI/GetDataHandlers.cs')
text = path.read_text(encoding='utf-8-sig')

old = 'byte itemFlags = args.Data.ReadByte();'
new = 'byte itemFlags = (byte)args.Data.ReadByte();'
if old not in text:
    raise RuntimeError('ItemDrop flags read pattern not found')
text = text.replace(old, new, 1)

npc_strike = '''\t\tprivate static bool HandleNpcStrike(GetDataHandlerArgs args)
\t\t{
\t\t\tshort id = (short)args.Data.ReadByte();
\t\t\tbyte generation = (byte)args.Data.ReadByte();
\t\t\tvar dmg = args.Data.ReadInt16();
\t\t\tvar knockback = args.Data.ReadSingle();
\t\t\tvar direction = (byte)(args.Data.ReadInt8() - 1);
\t\t\tvar crit = args.Data.ReadInt8();

\t\t\tbool AckAndHandle()
\t\t\t{
\t\t\t\t// Vanilla sends DamageNPCAck before validating the NPC generation.
\t\t\t\t// Only send it here when TShock consumes the packet; otherwise vanilla
\t\t\t\t// will process the packet and send exactly one acknowledgement itself.
\t\t\t\tNetMessage.TrySendData(162, args.Player.Index);
\t\t\t\treturn true;
\t\t\t}

\t\t\tif (id >= Main.npc.Length)
\t\t\t{
\t\t\t\tTShock.Log.ConsoleDebug(GetString("GetDataHandlers / HandleNpcStrike rejected out of bounds NPC index {0} for {1}",
\t\t\t\t\tid, args.Player.Name));
\t\t\t\treturn AckAndHandle();
\t\t\t}

\t\t\tif (Main.npc[id].generation != generation)
\t\t\t{
\t\t\t\tTShock.Log.ConsoleDebug(GetString("GetDataHandlers / HandleNpcStrike ignored stale NPC generation {0} for slot {1} from {2}",
\t\t\t\t\tgeneration, id, args.Player.Name));
\t\t\t\treturn AckAndHandle();
\t\t\t}

\t\t\tif (OnNPCStrike(args.Player, args.Data, id, direction, dmg, knockback, crit))
\t\t\t\treturn AckAndHandle();

\t\t\tif (Main.npc[id].townNPC && !args.Player.HasPermission(Permissions.hurttownnpc))
\t\t\t{
\t\t\t\targs.Player.SendErrorMessage(GetString("You do not have permission to hurt Town NPCs."));
\t\t\t\targs.Player.SendData(PacketTypes.NpcUpdate, "", id);
\t\t\t\tTShock.Log.ConsoleDebug(GetString($"GetDataHandlers / HandleNpcStrike rejected npc strike {args.Player.Name}"));
\t\t\t\treturn AckAndHandle();
\t\t\t}

\t\t\tif (Main.npc[id].netID == NPCID.EmpressButterfly)
\t\t\t{
\t\t\t\tif (!args.Player.HasPermission(Permissions.summonboss))
\t\t\t\t{
\t\t\t\t\targs.Player.SendErrorMessage(GetString("You do not have permission to summon the Empress of Light."));
\t\t\t\t\targs.Player.SendData(PacketTypes.NpcUpdate, "", id);
\t\t\t\t\tTShock.Log.ConsoleDebug(GetString($"GetDataHandlers / HandleNpcStrike rejected EoL summon from {args.Player.Name}"));
\t\t\t\t\treturn AckAndHandle();
\t\t\t\t}
\t\t\t\telse if (!TShock.Config.Settings.AnonymousBossInvasions)
\t\t\t\t{
\t\t\t\t\tTShock.Utils.Broadcast(GetString($"{args.Player.Name} summoned the Empress of Light!"), 175, 75, 255);
\t\t\t\t}
\t\t\t\telse
\t\t\t\t\tTShock.Utils.SendLogs(GetString($"{args.Player.Name} summoned the Empress of Light!"), Color.PaleVioletRed, args.Player);
\t\t\t}

\t\t\tif (Main.npc[id].netID == NPCID.CultistDevote || Main.npc[id].netID == NPCID.CultistArcherBlue)
\t\t\t{
\t\t\t\tif (!args.Player.HasPermission(Permissions.summonboss))
\t\t\t\t{
\t\t\t\t\targs.Player.SendErrorMessage(GetString("You do not have permission to summon the Lunatic Cultist!"));
\t\t\t\t\targs.Player.SendData(PacketTypes.NpcUpdate, "", id);
\t\t\t\t\tTShock.Log.ConsoleDebug(GetString($"GetDataHandlers / HandleNpcStrike rejected Cultist summon from {args.Player.Name}"));
\t\t\t\t\treturn AckAndHandle();
\t\t\t\t}
\t\t\t}
\t\t\treturn false;
\t\t}
'''
text = replace_method(text, 'HandleNpcStrike', 'HandleProjectileKill', npc_strike)

teleport = '''\t\tprivate static bool HandleTeleport(GetDataHandlerArgs args)
\t\t{
\t\t\tBitsByte flag = (BitsByte)args.Data.ReadByte();
\t\t\targs.Data.ReadInt16(); // Vanilla ignores the client-supplied entity id on the server.
\t\t\tshort id = (short)args.Player.Index;
\t\t\tVector2 position = args.Data.ReadVector2();
\t\t\tbyte style = args.Data.ReadInt8();

\t\t\tint type = 0;
\t\t\tint extraInfo = -1;
\t\t\tbool getPositionFromTarget = false;

\t\t\tif (flag[0])
\t\t\t\ttype += 1;
\t\t\tif (flag[1])
\t\t\t\ttype += 2;
\t\t\tif (flag[2])
\t\t\t\tgetPositionFromTarget = true;
\t\t\tif (flag[3])
\t\t\t\textraInfo = args.Data.ReadInt32();
\t\t\tif (getPositionFromTarget)
\t\t\t\tposition = Main.player[id].position;

\t\t\tif (OnTeleport(args.Player, args.Data, id, flag, position.X, position.Y, style, extraInfo))
\t\t\t\treturn true;

\t\t\tif (type == 0 && !args.Player.HasPermission(Permissions.rod))
\t\t\t{
\t\t\t\tTShock.Log.ConsoleDebug(GetString("GetDataHandlers / HandleTeleport rejected rod type {0} {1}", args.Player.Name, type));
\t\t\t\targs.Player.SendErrorMessage(GetString("You do not have permission to teleport using items."));
\t\t\t\targs.Player.Teleport(args.Player.TPlayer.position);
\t\t\t\treturn true;
\t\t\t}

\t\t\tif (type == 1 && id >= Main.maxNPCs)
\t\t\t{
\t\t\t\tTShock.Log.ConsoleDebug(GetString("GetDataHandlers / HandleTeleport rejected npc teleport {0} {1}", args.Player.Name, type));
\t\t\t\treturn true;
\t\t\t}

\t\t\tif (type == 2 && !args.Player.HasPermission(Permissions.wormhole))
\t\t\t{
\t\t\t\tTShock.Log.ConsoleDebug(GetString("GetDataHandlers / HandleTeleport rejected p2p wormhole permission {0} {1}", args.Player.Name, type));
\t\t\t\targs.Player.SendErrorMessage(GetString("You do not have permission to teleport using Wormhole Potions."));
\t\t\t\targs.Player.Teleport(args.Player.TPlayer.position);
\t\t\t\treturn true;
\t\t\t}

\t\t\t// Type 3 is the acknowledgement for a server-originated player teleport.
\t\t\treturn false;
\t\t}
'''
text = replace_method(text, 'HandleTeleport', 'HandleHealOther', teleport)

kill_portal = '''\t\tprivate static bool HandleKillPortal(GetDataHandlerArgs args)
\t\t{
\t\t\t// Packet 95 carries portal owner + portal side (ai[1]), not a projectile slot.
\t\t\tushort portalOwner = args.Data.ReadUInt16();
\t\t\tbyte portalSide = (byte)args.Data.ReadByte();

\t\t\tif (portalOwner >= Main.maxPlayers || portalSide > 1)
\t\t\t{
\t\t\t\tTShock.Log.ConsoleDebug(GetString("GetDataHandlers / HandleKillPortal rejected invalid portal key from {0}", args.Player.Name));
\t\t\t\treturn true;
\t\t\t}

\t\t\t// Vanilla intentionally sends this when a newly placed portal intersects another player's portal.
\t\t\treturn false;
\t\t}
'''
text = replace_method(text, 'HandleKillPortal', 'HandlePlayerPortalTeleport', kill_portal)

player_portal = '''\t\tprivate static bool HandlePlayerPortalTeleport(GetDataHandlerArgs args)
\t\t{
\t\t\targs.Data.ReadInt8(); // Vanilla ignores the client-supplied player id on the server.
\t\t\tbyte plr = (byte)args.Player.Index;
\t\t\tshort portalColorIndex = args.Data.ReadInt16();
\t\t\tfloat newPositionX = args.Data.ReadSingle();
\t\t\tfloat newPositionY = args.Data.ReadSingle();
\t\t\tfloat newVelocityX = args.Data.ReadSingle();
\t\t\tfloat newVelocityY = args.Data.ReadSingle();

\t\t\treturn OnPlayerTeleportThroughPortal(
\t\t\t\targs.Player,
\t\t\t\tplr,
\t\t\t\targs.Data,
\t\t\t\tnew Vector2(newPositionX, newPositionY),
\t\t\t\tnew Vector2(newVelocityX, newVelocityY),
\t\t\t\tportalColorIndex
\t\t\t);
\t\t}
'''
text = replace_method(text, 'HandlePlayerPortalTeleport', 'HandleNpcTeleportPortal', player_portal)

npc_portal = '''\t\tprivate static bool HandleNpcTeleportPortal(GetDataHandlerArgs args)
\t\t{
\t\t\t// Packet 100 is server-to-client only in vanilla 1.4.5.7.
\t\t\tTShock.Log.ConsoleDebug(GetString("GetDataHandlers / HandleNpcTeleportPortal rejected server-only packet from {0}", args.Player.Name));
\t\t\treturn true;
\t\t}
'''
text = replace_method(text, 'HandleNpcTeleportPortal', 'HandleGemLockToggle', npc_portal)

old = '''\t\t\t\tcase 3: // Shellphone (Spawn)
\t\t\t\t\tif (args.Player.ItemInHand.type != ItemID.ShellphoneSpawn && args.Player.SelectedItem.type != ItemID.ShellphoneSpawn)
\t\t\t\t\t{
\t\t\t\t\t\tTShock.Log.ConsoleDebug(GetString("GetDataHandlers / HandleTeleportationPotion rejected not holding the correct item {0} {1}", args.Player.Name, type));
\t\t\t\t\t\treturn true;
\t\t\t\t\t}
\t\t\t\t\tbreak;
\t\t\t}'''
new = '''\t\t\t\tcase 3: // Shellphone (Spawn)
\t\t\t\t\tif (args.Player.ItemInHand.type != ItemID.ShellphoneSpawn && args.Player.SelectedItem.type != ItemID.ShellphoneSpawn)
\t\t\t\t\t{
\t\t\t\t\t\tTShock.Log.ConsoleDebug(GetString("GetDataHandlers / HandleTeleportationPotion rejected not holding the correct item {0} {1}", args.Player.Name, type));
\t\t\t\t\t\treturn true;
\t\t\t\t\t}
\t\t\t\t\tbreak;
\t\t\t\tcase 4: // 1.4.5.7: server-side no-space recovery teleport
\t\t\t\t\tbreak;
\t\t\t\tdefault:
\t\t\t\t\tTShock.Log.ConsoleDebug(GetString("GetDataHandlers / HandleTeleportationPotion rejected unknown subtype {0} from {1}", type, args.Player.Name));
\t\t\t\t\treturn true;
\t\t\t}'''
if old not in text:
    raise RuntimeError('TeleportationPotion switch pattern not found')
text = text.replace(old, new, 1)
path.write_text(text, encoding='utf-8-sig')

path = Path('TShockAPI/TSPlayer.cs')
text = path.read_text(encoding='utf-8-sig')
old = '''\t\t\t\tvar msg = new ProjectileRemoveMsg
\t\t\t\t{
\t\t\t\t\tIndex = (short)index,
\t\t\t\t\tOwner = (byte)owner
\t\t\t\t};'''
new = '''\t\t\t\tvar generation = 0;
\t\t\t\tif (index >= 0 && index < Main.maxProjectiles)
\t\t\t\t{
\t\t\t\t\tvar projectile = Main.projectile[index];
\t\t\t\t\tif (projectile != null && projectile.owner == owner)
\t\t\t\t\t\tgeneration = projectile.key.Generation;
\t\t\t\t}

\t\t\t\tvar msg = new ProjectileRemoveMsg
\t\t\t\t{
\t\t\t\t\tIndex = (short)index,
\t\t\t\t\tOwner = (byte)owner,
\t\t\t\t\tGeneration = generation
\t\t\t\t};'''
if old not in text:
    raise RuntimeError('RemoveProjectile initializer pattern not found')
text = text.replace(old, new, 1)
path.write_text(text, encoding='utf-8-sig')

path = Path('TShockAPI/Bouncer.cs')
text = path.read_text(encoding='utf-8-sig')
pattern = r'\t\tinternal void OnPlayerPortalTeleport\(object sender, GetDataHandlers\.TeleportThroughPortalEventArgs args\)\n\t\t\{.*?(?=\n\t\t/// <summary>Handles the anti-cheat components of gem lock toggles\.)'
bouncer = '''\t\tinternal void OnPlayerPortalTeleport(object sender, GetDataHandlers.TeleportThroughPortalEventArgs args)
\t\t{
\t\t\tif (args.Player.Index != args.TargetPlayerIndex)
\t\t\t{
\t\t\t\tTShock.Log.ConsoleDebug(GetString("Bouncer / OnPlayerPortalTeleport rejected untargetable teleport from {0}", args.Player.Name));
\t\t\t\targs.Player.Disable(GetString("Malicious portal attempt."), DisableFlags.WriteToLogAndConsole);
\t\t\t\targs.Handled = true;
\t\t\t\treturn;
\t\t\t}

\t\t\tif (args.NewPosition.X > Main.maxTilesX * 16 || args.NewPosition.X < 0
\t\t\t\t|| args.NewPosition.Y > Main.maxTilesY * 16 || args.NewPosition.Y < 0
\t\t\t\t|| float.IsNaN(args.NewPosition.X) || float.IsNaN(args.NewPosition.Y)
\t\t\t\t|| float.IsInfinity(args.NewPosition.X) || float.IsInfinity(args.NewPosition.Y))
\t\t\t{
\t\t\t\tTShock.Log.ConsoleDebug(GetString("Bouncer / OnPlayerPortalTeleport rejected teleport out of bounds from {0}", args.Player.Name));
\t\t\t\targs.Handled = true;
\t\t\t\treturn;
\t\t\t}

\t\t\tif (args.PortalColorIndex < 0 || args.PortalColorIndex > 511)
\t\t\t{
\t\t\t\tTShock.Log.ConsoleDebug(GetString("Bouncer / OnPlayerPortalTeleport rejected invalid portal color from {0}", args.Player.Name));
\t\t\t\targs.Handled = true;
\t\t\t\treturn;
\t\t\t}

\t\t\tint portalOwner = args.PortalColorIndex / 2;
\t\t\tint portalSide = args.PortalColorIndex & 1;
\t\t\tvar exitPortal = Main.projectile.FirstOrDefault(p => p.active && p.type == ProjectileID.PortalGunGate
\t\t\t\t&& p.owner == portalOwner && (int)p.ai[1] == portalSide);
\t\t\tvar entryPortal = Main.projectile.FirstOrDefault(p => p.active && p.type == ProjectileID.PortalGunGate
\t\t\t\t&& p.owner == portalOwner && (int)p.ai[1] == 1 - portalSide);

\t\t\tif (exitPortal == null || entryPortal == null || Vector2.DistanceSquared(args.NewPosition, exitPortal.Center) > 128f * 128f)
\t\t\t{
\t\t\t\tTShock.Log.ConsoleDebug(GetString("Bouncer / OnPlayerPortalTeleport rejected teleport without a matching portal pair from {0}", args.Player.Name));
\t\t\t\targs.Handled = true;
\t\t\t\treturn;
\t\t\t}

\t\t\tif (args.Player.IsBeingDisabled() || args.Player.IsBouncerThrottled())
\t\t\t{
\t\t\t\tTShock.Log.ConsoleDebug(GetString("Bouncer / OnPlayerPortalTeleport rejected disabled/throttled from {0}", args.Player.Name));
\t\t\t\targs.Handled = true;
\t\t\t\treturn;
\t\t\t}
\t\t}
'''
text, count = re.subn(pattern, bouncer.rstrip(), text, count=1, flags=re.S)
if count != 1:
    raise RuntimeError(f'Could not replace OnPlayerPortalTeleport: {count} matches')
path.write_text(text, encoding='utf-8-sig')

#!/usr/bin/env python3
import json
import pathlib
import re
import urllib.request

DECOMP_COMMIT = "0459d7b61e35f15354a40fb9d1422d84e9bb4f2c"
BASE = f"https://raw.githubusercontent.com/JonataOliveiraa/Terraria1.4.5/{DECOMP_COMMIT}"


def fetch(path: str) -> str:
    with urllib.request.urlopen(f"{BASE}/{path}", timeout=30) as r:
        return r.read().decode("utf-8-sig")


def extract_braced(text: str, start: int) -> str:
    brace = text.find("{", start)
    if brace < 0:
        return ""
    depth = 0
    in_string = False
    verbatim = False
    esc = False
    i = brace
    while i < len(text):
        c = text[i]
        if in_string:
            if verbatim:
                if c == '"' and i + 1 < len(text) and text[i + 1] == '"':
                    i += 2
                    continue
                if c == '"':
                    in_string = False
                    verbatim = False
            else:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_string = False
        else:
            if c == '@' and i + 1 < len(text) and text[i + 1] == '"':
                in_string = True
                verbatim = True
                i += 2
                continue
            if c == '"':
                in_string = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return text[brace:i + 1]
        i += 1
    return text[brace:]


def method_body(text: str, name: str) -> str:
    m = re.search(rf"private\s+static\s+bool\s+{re.escape(name)}\s*\(", text)
    if not m:
        return ""
    return extract_braced(text, m.start())


def packet_cases(message_buffer: str):
    # The top-level packet switch is `switch (num2)` in GetData(). Extract only that switch.
    switch_pos = message_buffer.find("switch (num2)")
    if switch_pos < 0:
        raise RuntimeError("Could not find packet switch")
    switch_body = extract_braced(message_buffer, switch_pos)
    lines = switch_body.splitlines()
    case_rows = []
    for i, line in enumerate(lines):
        m = re.match(r"^(\s*)case\s+(\d+)\s*:", line)
        if m:
            case_rows.append((i, len(m.group(1)), int(m.group(2))))
    if not case_rows:
        raise RuntimeError("No packet cases found")
    base_indent = min(indent for _, indent, _ in case_rows)
    top = [(i, n) for i, indent, n in case_rows if indent == base_indent]
    out = {}
    for idx, (line_no, packet_id) in enumerate(top):
        end = top[idx + 1][0] if idx + 1 < len(top) else len(lines)
        out[packet_id] = "\n".join(lines[line_no:end])
    return out


READ_RE_TSHOCK = re.compile(r"args\.Data\.(Read[A-Za-z0-9_]+)\s*\(")
READ_RE_VANILLA = re.compile(r"this\.reader\.(Read[A-Za-z0-9_]+)\s*\(")

WIDTHS = {
    "ReadByte": 1, "ReadSByte": 1, "ReadInt8": 1, "ReadUInt8": 1, "ReadBoolean": 1,
    "ReadInt16": 2, "ReadUInt16": 2,
    "ReadInt32": 4, "ReadUInt32": 4, "ReadSingle": 4,
    "ReadInt64": 8, "ReadUInt64": 8, "ReadDouble": 8,
    "ReadVector2": 8, "ReadRGB": 3,
}

BYTE_EQUIV = {
    "ReadInt8": "B", "ReadUInt8": "B", "ReadByte": "B", "ReadSByte": "B", "ReadBoolean": "B",
    "ReadInt16": "H", "ReadUInt16": "H",
    "ReadInt32": "I", "ReadUInt32": "I", "ReadSingle": "I",
    "ReadInt64": "Q", "ReadUInt64": "Q", "ReadDouble": "Q",
    "ReadVector2": "VV", "ReadRGB": "RGB",
    "ReadString": "STR",
}


def byte_shape(seq):
    return [BYTE_EQUIV.get(x, x) for x in seq]


def common_prefix(a, b):
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


def static_width(seq):
    total = 0
    complete = True
    for x in seq:
        if x not in WIDTHS:
            complete = False
        else:
            total += WIDTHS[x]
    return total, complete


def parse_packet_types(text: str):
    return {name: int(num) for name, num in re.findall(r"^\s*(\w+)\s*=\s*(\d+)\s*,?", text, re.M)}


def parse_message_ids(text: str):
    result = {}
    for name, num in re.findall(r"public\s+const\s+byte\s+(\w+)\s*=\s*(\d+)", text):
        result[int(num)] = name
    return result


def main():
    tshock = pathlib.Path("TShockAPI/GetDataHandlers.cs").read_text(encoding="utf-8-sig")
    packet_types_text = pathlib.Path("TerrariaServerAPI/TerrariaApi.Server/PacketTypes.cs").read_text(encoding="utf-8-sig")
    packet_types = parse_packet_types(packet_types_text)
    registrations = re.findall(r"\{\s*PacketTypes\.(\w+)\s*,\s*(\w+)\s*\}", tshock)

    message_buffer = fetch("MessageBuffer.cs")
    message_ids_text = fetch("ID/MessageID.cs")
    vanilla_names = parse_message_ids(message_ids_text)
    cases = packet_cases(message_buffer)

    report = []
    for packet_name, handler in registrations:
        packet_id = packet_types.get(packet_name)
        body = method_body(tshock, handler)
        vanilla = cases.get(packet_id, "") if packet_id is not None else ""
        t_reads = READ_RE_TSHOCK.findall(body)
        v_reads = READ_RE_VANILLA.findall(vanilla)
        t_shape = byte_shape(t_reads)
        v_shape = byte_shape(v_reads)
        prefix = common_prefix(t_shape, v_shape)

        if not body:
            status = "HANDLER_NOT_FOUND"
        elif not vanilla:
            status = "VANILLA_CASE_NOT_FOUND"
        elif t_shape == v_shape:
            status = "EXACT_STATIC_ORDER"
        elif prefix == len(t_shape) and len(t_shape) <= len(v_shape):
            status = "TSHOCK_PREFIX"
        elif prefix >= min(2, len(t_shape), len(v_shape)):
            status = "DIVERGES_AFTER_PREFIX"
        else:
            status = "EARLY_DIVERGENCE"

        # Vanilla often overwrites a client-supplied entity/player id with whoAmI.
        vanilla_canonicalizes = "this.whoAmI" in vanilla
        tshock_canonicalizes = ("args.Player.Index" in body or "args.TPlayer.whoAmI" in body)
        canonicalization_flag = vanilla_canonicalizes and not tshock_canonicalizes

        # Heuristic: packets whose vanilla block only performs work in client netmode are server->client.
        client_only_hint = bool(re.search(r"if \(Main\.netMode != 1\)\s*\n\s*break;", vanilla[:350]))

        tw, tc = static_width(t_reads)
        vw, vc = static_width(v_reads)
        report.append({
            "packet": packet_name,
            "id": packet_id,
            "vanilla_name": vanilla_names.get(packet_id),
            "handler": handler,
            "status": status,
            "canonicalization_flag": canonicalization_flag,
            "client_only_hint": client_only_hint,
            "tshock_reads": t_reads,
            "vanilla_reads": v_reads,
            "tshock_static_width": tw,
            "vanilla_static_width": vw,
            "tshock_width_complete": tc,
            "vanilla_width_complete": vc,
        })

    pathlib.Path("packet-audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    suspicious = [r for r in report if r["status"] not in ("EXACT_STATIC_ORDER", "TSHOCK_PREFIX") or r["canonicalization_flag"] or r["client_only_hint"]]
    lines = [
        f"# TShock packet handler audit vs Terraria 1.4.5.7 ({DECOMP_COMMIT})",
        "",
        f"Registered handlers: **{len(report)}**",
        f"Heuristically suspicious: **{len(suspicious)}**",
        "",
        "The comparison is intentionally conservative: conditional fields and different client/server branches can create false positives. Every suspicious row must be manually reviewed.",
        "",
        "| ID | PacketTypes | Vanilla MessageID | Handler | Static comparison | whoAmI flag | client-only hint |",
        "|---:|---|---|---|---|:---:|:---:|",
    ]
    for r in report:
        lines.append(f"| {r['id']} | {r['packet']} | {r['vanilla_name']} | {r['handler']} | {r['status']} | {'YES' if r['canonicalization_flag'] else ''} | {'YES' if r['client_only_hint'] else ''} |")
    lines += ["", "## Suspicious details", ""]
    for r in suspicious:
        lines += [
            f"### {r['id']} {r['packet']} -> {r['handler']}",
            f"Vanilla name: `{r['vanilla_name']}`; status: `{r['status']}`; whoAmI flag: `{r['canonicalization_flag']}`; client-only hint: `{r['client_only_hint']}`",
            f"TShock reads: `{' -> '.join(r['tshock_reads']) or '(none)'}`",
            f"Vanilla reads: `{' -> '.join(r['vanilla_reads']) or '(none)'}`",
            "",
        ]
    pathlib.Path("packet-audit.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

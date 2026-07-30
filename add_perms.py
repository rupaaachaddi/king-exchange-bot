import re

commands_to_protect = [
    "manage", "upi", "addy", "mmqr", "addupi", "addaddy", "addid", "delupi", "deladdy", "delid", "id_cmd",
    "vouch", "dn", "transcript_cmd", "unclaim", "adduser", "removeuser", "close", "screenshot",
    "stats", "profile", "deal_summary", "leaderboard"
]

with open("bot.py", "r") as f:
    lines = f.readlines()

out = []
i = 0
while i < len(lines):
    line = lines[i]
    
    # 1. Add check_staff definition after is_staff
    if line.startswith("def is_staff(ctx):"):
        out.append(line)
        # Read the rest of the function
        i += 1
        while i < len(lines) and lines[i].startswith("    "):
            out.append(lines[i])
            i += 1
        out.append("\nfrom discord.ext import commands\n")
        out.append("def check_staff():\n")
        out.append("    def predicate(ctx):\n")
        out.append("        if is_staff(ctx):\n")
        out.append("            return True\n")
        out.append("        raise commands.CheckFailure(\"❌ Staff only.\")\n")
        out.append("    return commands.check(predicate)\n")
        continue

    # 2. Add @check_staff() before @bot.command for targeted commands
    m = re.match(r'^async def ([a-zA-Z0-9_]+)\(', line)
    if m:
        func_name = m.group(1)
        if func_name in commands_to_protect:
            # Look backwards for the @bot.command line and insert @check_staff() right after it
            for j in range(len(out)-1, -1, -1):
                if "@bot.command" in out[j]:
                    out.insert(j+1, "@check_staff()\n")
                    break
                    
    # 3. Protect implicit on_message commands
    if line.strip() == "if cmd.startswith(\"upi\") and len(cmd) > 3 and cmd[3:].isdigit():":
        out.append(line)
        out.append("            if not is_staff(message):\n")
        out.append("                await message.channel.send(\"❌ Staff only.\")\n")
        out.append("                return\n")
        i += 1
        continue
        
    if line.strip() == "if matched_addy:":
        out.append("            if (matched_addy or matched_id) and not is_staff(message):\n")
        out.append("                await message.channel.send(\"❌ Staff only.\")\n")
        out.append("                return\n")
        out.append(line)
        i += 1
        continue
        
    # 4. Handle CheckFailure in on_command_error
    if line.strip() == "elif isinstance(error, commands.CommandNotFound):":
        out.append("    elif isinstance(error, commands.CheckFailure):\n")
        out.append("        await ctx.send(str(error), delete_after=5)\n")
        out.append(line)
        i += 1
        continue

    out.append(line)
    i += 1

with open("bot.py", "w") as f:
    f.writelines(out)

print("Updated bot.py with staff checks!")

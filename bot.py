from discord import interactions
from discord import interactions
from aiohttp import client_middlewares
from aiohttp import client_exceptions
from discord import interactions
from discord import interactions
from aiohttp import client_middlewares
from aiohttp import client_middlewares
from discord import interactions
from discord import interactions
from discord import app_commands
from discord import interactions
print("===== VERSION 24 JULY =====", flush=True)
import discord
from discord.ext import commands
import os
import asyncio
import chat_exporter
import io
import urllib.parse
from datetime import datetime, timedelta
import pytz

IST = pytz.timezone("Asia/Kolkata")
from dotenv import load_dotenv
import motor.motor_asyncio

# ── Load .env ─────────────────────────────────────────────────────────────────
load_dotenv()

BOT_TOKEN              = os.getenv("BOT_TOKEN")
GUILD_ID               = int(os.getenv("GUILD_ID", 0))
TICKETS_CATEGORY_NAME  = os.getenv("TICKETS_CATEGORY_NAME", "Tickets")
ADMIN_ARCHIVES_ID      = int(os.getenv("ADMIN_ARCHIVES_ID") or 0)
I2C_ARCHIVES_ID        = int(os.getenv("I2C_ARCHIVES_ID") or 0)
C2I_ARCHIVES_ID        = int(os.getenv("C2I_ARCHIVES_ID") or 0)
C2C_ARCHIVES_ID        = int(os.getenv("C2C_ARCHIVES_ID") or 0)
I2C_ROLE_ID            = int(os.getenv("I2C_ROLE_ID") or 0)
C2I_ROLE_ID            = int(os.getenv("C2I_ROLE_ID") or 0)
C2C_ROLE_ID            = int(os.getenv("C2C_ROLE_ID") or 0)
TOS_CHANNEL_ID         = int(os.getenv("TOS_CHANNEL_ID") or 0)
VOUCH_CHANNEL_ID       = int(os.getenv("VOUCH_CHANNEL_ID") or 0)
VOUCH_PENDING_CATEGORY = os.getenv("VOUCH_PENDING_CATEGORY", "VOUCH PENDING")
MONGODB_URI            = os.getenv("MONGODB_URI")
OWNER_ID = int(os.getenv("OWNER_ID") or 0)
OWNER_ID_2 = int(os.getenv("OWNER_ID_2") or 0)
EXCHANGE_HISTORY_CHANNEL_ID = int(os.getenv("EXCHANGE_HISTORY_CHANNEL_ID"))
MM_CATEGORY_ID = int(os.getenv("MM_CATEGORY_ID"))
MM_ROLE_ID     = int(os.getenv("MM_ROLE_ID"))
SUPPORT_ARCHIVES_ID = int(os.getenv("SUPPORT_ARCHIVES_ID") or 0)
DONE_CATEGORY_ID = int(os.getenv("DONE_CATEGORY_ID"))
CASH_EXCHANGE_ARCHIVES_ID = int(os.getenv("CASH_EXCHANGE_ARCHIVES_ID") or 0)
CASH_EXCHANGE_ROLE_ID     = int(os.getenv("CASH_EXCHANGE_ROLE_ID") or 0)

# ── MongoDB setup ─────────────────────────────────────────────────────────────
mongo_client = motor.motor_asyncio.AsyncIOMotorClient(
    MONGODB_URI,
    serverSelectionTimeoutMS=30000,
    connectTimeoutMS=30000,
    socketTimeoutMS=30000
)
db           = mongo_client["primebot"]

tickets_col      = db["tickets"]
counters_col     = db["counters"]
rates_col        = db["rates"]
wallets_col      = db["wallets"]
stats_col        = db["stats"]
client_stats_col = db["client_stats"]
limits_col       = db["limits"]
# tax_col          = db["tax"]  # TAX SYSTEM DISABLED

# ── DB helpers ────────────────────────────────────────────────────────────────
async def get_doc(col, key: str):
    doc = await col.find_one({"_id": key})
    return doc if doc else None

async def set_doc(col, key: str, data: dict):
    data["_id"] = key
    await col.replace_one({"_id": key}, data, upsert=True)

async def get_all(col):
    docs = {}
    async for doc in col.find():
        k = doc.pop("_id")
        docs[k] = doc
    return docs

# ── Bot setup ─────────────────────────────────────────────────────────────────
def clean_float(value):
    try:
        return float("".join(c for c in str(value) if c.isdigit() or c == '.'))
    except (ValueError, TypeError):
        return 0.0
    
async def get_c2i_rate(amount: float) -> float:
    rates = await get_doc(rates_col, "rates") or {}
    if amount >= 100:
        return clean_float(rates.get("c2i_high_rate", rates.get("c2i_rate", "95")))
    return clean_float(rates.get("c2i_rate", "95"))

async def get_cash_c2i_rate(amount: float) -> float:
    rates = await get_doc(rates_col, "rates") or {}

    if amount >= 100:
        return clean_float(
            rates.get(
                "cash_c2i_high_rate",
                rates.get(
                    "cash_c2i_rate",
                    rates.get("c2i_high_rate", "95")
                )
            )
        )

    return clean_float(
        rates.get(
            "cash_c2i_rate",
            rates.get("c2i_rate", "95")
        )
    )
    
def normalize_wallet_item(item):
    "Convert old string format to new dict format."
    if isinstance(item, str):
        return {"label": "Entry", "value": item}
    return item

def is_owner(ctx):
    return ctx.author.id in (OWNER_ID, OWNER_ID_2)

def is_staff(ctx):
    if ctx.author.id == OWNER_ID:
        return True
    user_roles = [r.id for r in getattr(ctx.author, "roles", [])]
    return any(rid in user_roles for rid in [I2C_ROLE_ID, C2I_ROLE_ID, C2C_ROLE_ID] if rid != 0)

from discord.ext import commands
def check_staff():
    def predicate(ctx):
        if is_staff(ctx):
            return True
        raise commands.CheckFailure("❌ Staff only.")
    return commands.check(predicate)
def check_owner():
    def predicate(ctx):
        if is_owner(ctx):
            return True
        raise commands.CheckFailure("❌ Owner only.")
    return commands.check(predicate)

async def update_stats(staff_id, amount, trade_type):
    uid  = str(staff_id)
    doc  = await get_doc(stats_col, uid) or {"trades": []}
    doc["trades"].append({
        "time":   datetime.now().isoformat(),
        "amount": clean_float(amount),
        "type":   trade_type
    })
    await set_doc(stats_col, uid, doc)


async def send_exchange_history(ctx, client, trade_type, amt_clean, asset):
    history_channel = ctx.guild.get_channel(EXCHANGE_HISTORY_CHANNEL_ID)
    if not history_channel:
        return

    ticket_doc = await get_doc(tickets_col, str(ctx.channel.id))
    ticket_number = ticket_doc.get("ticket_number") if ticket_doc else None
    deal_id = f"#{ticket_number:04d}" if ticket_number else "#0000"

    type_display_map = {
        "i2c": "INR To Crypto",
        "c2i": "Crypto To INR",
        "c2c": "Crypto To Crypto",
    }
    type_display = type_display_map.get(trade_type, trade_type.upper())

    rates_doc = await get_doc(rates_col, "rates") or {}

    if trade_type in ("i2c", "cash_i2c"):
        if trade_type == "cash_i2c":
            rate = clean_float(
                rates_doc.get(
                    "cash_i2c_rate",
                    rates_doc.get("i2c_rate", "99")
                )
            )
        else:
            rate = clean_float(
                rates_doc.get("i2c_rate", "99")
        )
        crypto_amt = round(amt_clean / rate, 2) if rate > 0 else 0
        send_display    = f"₹{amt_clean:,.2f}"
        receive_display = f"{crypto_amt:,.2f} {asset.upper()}"

    elif trade_type == "c2i":
        rate = await get_c2i_rate(amt_clean)
        inr_amt = round(amt_clean * rate, 2) if rate > 0 else 0
        send_display    = f"{amt_clean:,.2f} {asset.upper()}"
        receive_display = f"₹{inr_amt:,.2f}"

    else:  # c2c
        parts = asset.upper().split("→") if "→" in asset else asset.upper().split(" ")
        send_asset    = parts[0].strip() if len(parts) > 0 else asset.upper()
        receive_asset = parts[1].strip() if len(parts) > 1 else asset.upper()
        fee_pct  = clean_float(rates_doc.get("c2c_rate", "3"))
        recv_amt = round(amt_clean * (1 - fee_pct / 100), 2)
        send_display    = f"{amt_clean:,.2f} {send_asset}"
        receive_display = f"{recv_amt:,.2f} {receive_asset}"

    embed = discord.Embed(color=0x2b2d31)
    embed.description = "<a:check:1530250663206977701> **Deal Verified**"
    embed.add_field(name="<a:ticket:1530269895517016275> Deal ID", value=f"`{deal_id}`", inline=True)
    embed.add_field(name="<a:arrowyellow:1530241815121232072> Type", value=type_display, inline=True)
    embed.add_field(name="<a:crownyellow:1530251567880736788> Exchanger", value=ctx.author.mention, inline=True)
    embed.add_field(name="<a:money:1530269856308531380> You Send", value=send_display, inline=True)
    embed.add_field(name="<a:money:1530269856308531380> You Receive", value=receive_display, inline=True)
    if ctx.guild.icon:
        embed.set_thumbnail(url=ctx.guild.icon.url)
    embed.set_footer(text=f"King Exchange & MM • Exchange • {datetime.now(IST).strftime('Today at %I:%M %p')}")

    await history_channel.send(embed=embed)
# ── TAX SYSTEM DISABLED ──────────────────────────────────────────────────────
# async def update_tax(staff_id: int, amount: float):
#     uid = str(staff_id)
#     doc = await get_doc(tax_col, uid) or {"total_tax": 0.0, "paid_tax": 0.0, "history": []}
#     doc["total_tax"] = round(doc["total_tax"] + amount, 4)
#     doc["history"].append({
#         "time":   datetime.now().isoformat(),
#         "amount": amount,
#         "type":   "added"
#     })
#     await set_doc(tax_col, uid, doc)
# ─────────────────────────────────────────────────────────────────────────────

intents = discord.Intents.all()

async def get_prefix(bot, message):
    if message.content.startswith("?vouch"):
        return "?"
    return "+"

bot = commands.Bot(command_prefix=get_prefix, intents=intents, help_command=None)

# ═══════════════════════════════════════════════════════════════════════════════
#  MODALS
# ═══════════════════════════════════════════════════════════════════════════════

class INRToCryptoModal(discord.ui.Modal, title="INR To Crypto Exchange"):
    amt    = discord.ui.TextInput(label="Please Enter The Amount in ₹", placeholder="e.g. 5000")
    asset  = discord.ui.TextInput(label="Which Crypto Do You Want To Buy?", placeholder="LTC, BTC, USDT, SOL")
    method = discord.ui.TextInput(label="Which payment application are you using?", placeholder="UPI / GPay / PhonePe")

    async def on_submit(self, interaction: discord.Interaction):
        await open_ticket(interaction, e_type="i2c", amt=self.amt.value, asset=self.asset.value, method=self.method.value)

class CryptoToINRModal(discord.ui.Modal, title="Crypto To INR Exchange"):
    amt    = discord.ui.TextInput(label="Please Enter The Amount in $", placeholder="e.g. 100")
    asset  = discord.ui.TextInput(label="Which Crypto Do You Want To Sell?", placeholder="LTC, BTC, USDT, SOL")
    wallet = discord.ui.TextInput(label="Which Crypto Wallet You Are Using?", placeholder="Binance, Trust Wallet, Cwallet")

    async def on_submit(self, interaction: discord.Interaction):
        await open_ticket(interaction, e_type="c2i", amt=self.amt.value, asset=self.asset.value, method=self.wallet.value)

class CryptoToCryptoModal(discord.ui.Modal, title="Crypto To Crypto Exchange"):
    amt       = discord.ui.TextInput(label="Please Enter The Amount in $", placeholder="e.g. 100")
    sending   = discord.ui.TextInput(label="Crypto Name You Are Sending?", placeholder="e.g. BTC")
    receiving = discord.ui.TextInput(label="Crypto Name You Wanna Receive?", placeholder="e.g. USDT")

    async def on_submit(self, interaction: discord.Interaction):
        await open_ticket(interaction, e_type="c2c", amt=self.amt.value,
                          asset=f"{self.sending.value}→{self.receiving.value}", method="C2C")

class CashI2CModal(discord.ui.Modal, title="🛡️ CASH Exchange — INR To Crypto"):
    amt    = discord.ui.TextInput(label="Please Enter The Amount in ₹", placeholder="e.g. 5000 (minimum ≈ $50)")
    asset  = discord.ui.TextInput(label="Which Crypto Do You Want To Buy?", placeholder="LTC, BTC, USDT, SOL")
    method = discord.ui.TextInput(label="Which payment application are you using?", placeholder="UPI / GPay / PhonePe")

    async def on_submit(self, interaction: discord.Interaction):
        await open_ticket(interaction, e_type="cash_i2c", amt=self.amt.value, asset=self.asset.value, method=self.method.value)

class CashC2IModal(discord.ui.Modal, title="🛡️ CASH Exchange — Crypto To INR"):
    amt    = discord.ui.TextInput(label="Please Enter The Amount in $", placeholder="e.g. 100 (minimum $50)")
    asset  = discord.ui.TextInput(label="Which Crypto Do You Want To Sell?", placeholder="LTC, BTC, USDT, SOL")
    wallet = discord.ui.TextInput(label="Which Crypto Wallet You Are Using?", placeholder="Binance, Trust Wallet, Cwallet")

    async def on_submit(self, interaction: discord.Interaction):
        await open_ticket(interaction, e_type="cash_c2i", amt=self.amt.value, asset=self.asset.value, method=self.wallet.value)

class MMModal(discord.ui.Modal, title="Middleman Request"):
    amt         = discord.ui.TextInput(label="Deal Amount", placeholder="e.g. 5000 or 100")
    other_party = discord.ui.TextInput(label="Other Party (Username/Mention/ID)", placeholder="@username or ID")
    details     = discord.ui.TextInput(label="Deal Details", placeholder="What are you exchanging?", style=discord.TextStyle.paragraph)

    def __init__(self, mm_type: str):
        super().__init__()
        self.mm_type = mm_type

    async def on_submit(self, interaction: discord.Interaction):
        await open_mm_ticket(
            interaction, mm_type=self.mm_type,
            amt=self.amt.value, other_party=self.other_party.value, details=self.details.value
        )

class SupportHelpModal(discord.ui.Modal, title="Support Ticket"):
    query = discord.ui.TextInput(
        label="How can we help you?",
        placeholder="Describe your query or issue...",
        style=discord.TextStyle.paragraph
    )

    async def on_submit(self, interaction: discord.Interaction):
        await open_support_ticket(interaction, s_type="support", details={"query": self.query.value})

class SupportReportModal(discord.ui.Modal, title="Report Exchanger"):
    exchanger = discord.ui.TextInput(
        label="Which exchanger are you reporting?",
        placeholder="Username, mention, or ID"
    )
    reason = discord.ui.TextInput(
        label="Reason & Evidence Details",
        placeholder="Explain what happened and details of proof...",
        style=discord.TextStyle.paragraph
    )

    async def on_submit(self, interaction: discord.Interaction):
        await open_support_ticket(interaction, s_type="report", details={
            "exchanger": self.exchanger.value,
            "reason": self.reason.value
        })


# ═══════════════════════════════════════════════════════════════════════════════
#  TICKET OPENER
def owner_only_slash():
    async def predicate(interaction: discord.Interaction):
        if interaction.user.id in (OWNER_ID, OWNER_ID_2):
            return True
        await interaction.response.send_message("❌ Owner only.", ephemeral=True)
        return False
    return app_commands.check(predicate)
# ═══════════════════════════════════════════════════════════════════════════════

async def open_ticket(interaction: discord.Interaction, e_type: str, amt: str, asset: str, method: str):
    await interaction.response.defer(ephemeral=True)

    # Check existing exchange ticket (i2c/c2i/c2c/cash_i2c/cash_c2i) — max 1 at a time
    # Tickets already moved to review (Done category) don't count as "open"
    all_tickets = await get_all(tickets_col)
    exchange_open = sum(
        1 for t in all_tickets.values()
        if t.get("client") == interaction.user.id
        and t.get("type") in ("i2c", "c2i", "c2c", "cash_i2c", "cash_c2i")
        and not t.get("review_pending")
    )
    if exchange_open >= 1:
        return await interaction.followup.send(
            "❌ You already have an open exchange ticket. Please close it before opening a new one.",
            ephemeral=True
        )

    # ── Minimum amount validation ──────────────────────────────────────────
    amt_float = clean_float(amt)
    rates_doc = await get_doc(rates_col, "rates") or {}

    if e_type == "i2c":
        i2c_rate_val = clean_float(rates_doc.get("i2c_rate", "99"))
        usd_equiv = round(amt_float / i2c_rate_val, 4) if i2c_rate_val > 0 else 0
        if usd_equiv < 1:
            min_inr = round(i2c_rate_val * 1, 2)
            return await interaction.followup.send(
                f"❌ Amount too low. Minimum exchange is **$1** (≈ ₹{min_inr}).", ephemeral=True)
    elif e_type == "c2i":
        if amt_float < 1:
            return await interaction.followup.send(
                "❌ Amount too low. Minimum exchange is **$1**.", ephemeral=True)
    elif e_type == "c2c":
        if amt_float < 1:
            return await interaction.followup.send(
                "❌ Amount too low. Minimum exchange is **$1**.", ephemeral=True)
    elif e_type == "cash_i2c":
        i2c_rate_val = clean_float(
            rates_doc.get(
                "cash_i2c_rate",
                rates_doc.get("i2c_rate", "99")
            )
        )
        usd_equiv = round(amt_float / i2c_rate_val, 4) if i2c_rate_val > 0 else 0
        if usd_equiv < 50:
            min_inr = round(i2c_rate_val * 50, 2)
            return await interaction.followup.send(
                f"🛡️ Cash Exchange requires a **minimum of $50** (≈ ₹{min_inr:,.0f}). Your amount is too low.", ephemeral=True)
    elif e_type == "cash_c2i":
        if amt_float < 50:
            return await interaction.followup.send(
                "🛡️ Cash Exchange requires a **minimum of $50**. Your amount is too low.", ephemeral=True)

    # Ticket counter
    counter_doc = await get_doc(counters_col, "counters") or {"i2c": 1, "c2i": 0, "c2c": 0}
    counter_doc[e_type] = counter_doc.get(e_type, 0) + 1
    ticket_number = counter_doc[e_type]
    await set_doc(counters_col, "counters", counter_doc)

    

    type_info = {
        "i2c":      ("🎫┃i2c",      "INR → Crypto",        "INR TO CRYPTO"),
        "c2i":      ("💵┃c2i",      "Crypto → INR",         "CRYPTO TO INR"),
        "c2c":      ("🏦┃c2c",      "Crypto → Crypto",      "CRYPTO TO CRYPTO"),
        "cash_i2c": ("🛡️┃cash-i2c", "🛡️ Cash INR → Crypto", "CASH EXCHANGE"),
        "cash_c2i": ("🛡️┃cash-c2i", "🛡️ Cash Crypto → INR", "CASH EXCHANGE"),
    }
    channel_prefix, type_display, category_name = type_info[e_type]
    channel_name = f"{channel_prefix}-{ticket_number}"
    guild        = interaction.guild
    cat          = discord.utils.get(guild.categories, name=category_name) \
                   or await guild.create_category(category_name)

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user:   discord.PermissionOverwrite(view_channel=True, send_messages=True),
        guild.me:           discord.PermissionOverwrite(view_channel=True, send_messages=True),
    }
    channel = await guild.create_text_channel(channel_name, category=cat, overwrites=overwrites)

    await set_doc(tickets_col, str(channel.id), {
        "client": interaction.user.id, "exchanger": None,
        "amount": amt, "asset": asset, "type": e_type,
        "ticket_number": ticket_number, "vouch_pending": False
    })

    # Rates
    rates_doc = await get_doc(rates_col, "rates") or {}
    i2c_rate  = rates_doc.get("i2c_rate", "99").replace("/$", "")
    c2i_rate  = rates_doc.get("c2i_rate", "95").replace("/$", "")
    c2i_high  = rates_doc.get("c2i_high_rate", c2i_rate).replace("/$", "")
    c2c_rate  = rates_doc.get("c2c_rate", "3").replace("%", "")

    tos_channel = guild.get_channel(TOS_CHANNEL_ID)
    tos_mention = tos_channel.mention if tos_channel else "#tos"

    role_map = {
        "i2c": I2C_ROLE_ID, "c2i": C2I_ROLE_ID, "c2c": C2C_ROLE_ID,
        "cash_i2c": CASH_EXCHANGE_ROLE_ID or I2C_ROLE_ID,
        "cash_c2i": CASH_EXCHANGE_ROLE_ID or C2I_ROLE_ID,
    }
    role     = guild.get_role(role_map.get(e_type, 0))

    # Send role & client ping in single line
    ping_text = f"{interaction.user.mention} {role.mention}" if role else interaction.user.mention
    await channel.send(content=ping_text)

    # Format currency conversion
    if e_type in ("i2c", "cash_i2c"):
        amt_display = f"₹{amt_float:g}"
        if e_type == "i2c":
            i2c_rate_val = clean_float(i2c_rate)
        else:
            i2c_rate_val = clean_float(
                rates_doc.get(
                    "cash_i2c_rate",
                    rates_doc.get("i2c_rate", "99")
        )
    )
        if i2c_rate_val > 0:
            usd_equiv = round(amt_float / i2c_rate_val, 2)
            amt_display = f"₹{amt_float:g} (≈ ${usd_equiv:.2f})"
        display_rate = (
            rates_doc.get("cash_i2c_rate", i2c_rate)
            if e_type == "cash_i2c"
            else i2c_rate
        )
        rate_str = f"`{display_rate}/$` (Any Amount)"
    elif e_type in ("c2i", "cash_c2i"):
        if e_type == "cash_c2i":
            c2i_rate_val = await get_cash_c2i_rate(amt_float)
        else:
            c2i_rate_val = await get_c2i_rate(amt_float)
        if c2i_rate_val > 0:
            inr_equiv = int(round(amt_float * c2i_rate_val))
            amt_display = f"${amt_float:g} (≈ ₹{inr_equiv:,})"
        if e_type == "cash_c2i":
            low = rates_doc.get("cash_c2i_rate", c2i_rate)
            high = rates_doc.get("cash_c2i_high_rate", c2i_high)
        else:
            low = c2i_rate
            high = c2i_high
        rate_str = f"Below $100: `{low}/$` | Above $100: `{high}/$`"
    else:
        amt_display = f"${amt_float:g}"
        rate_str = f"`{c2c_rate}% Fees + Tx Fees`"

    is_cash = e_type in ("cash_i2c", "cash_c2i")
    embed_color = 0x2b2d31
    embed = discord.Embed(title=f"<a:crownyellow:1530251567880736788> KING EXCHANGE • {type_display}", color=embed_color)
    cash_note = "\n🛡️ **Cash Exchange** — Your deal is handled with extra care. Minimum $50." if is_cash else ""
    embed.description = (
        f"<a:peachboba:1530266777890590973> Welcome {interaction.user.mention} to **KING EXCHANGE & MM**!\n"
        f"Please make sure to read {tos_mention} before proceeding with your trade.{cash_note}\n\n"
    )

    embed.add_field(
        name="<a:peachboba:1530266777890590973> Client & Ticket ID",
        value=f"{interaction.user.mention}\n`#{ticket_number:04d}`",
        inline=True
    )
    embed.add_field(
        name="<a:money:1530269856308531380> Amount & Asset",
        value=f"`{amt_display}`\n`{asset.upper()}`",
        inline=True
    )
    embed.add_field(
        name="<a:creditcard:1530269729254539405> Payment & Type",
        value=f"`{method.upper()}`\n`{type_display}`",
        inline=True
    )

    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    else:
        embed.set_thumbnail(url=interaction.user.display_avatar.url)

    embed.set_footer(text="King Exchange & MM • Fast, Secure & Trusted")
    await channel.send(embed=embed, view=ClaimView())
    await interaction.followup.send(f"✅ Ticket created: {channel.mention}", ephemeral=True)

async def open_mm_ticket(interaction: discord.Interaction, mm_type: str, amt: str, other_party: str, details: str):
    await interaction.response.defer(ephemeral=True)

    all_tickets = await get_all(tickets_col)
    mm_open = sum(
        1 for t in all_tickets.values()
        if t.get("client") == interaction.user.id
        and t.get("type") == "mm"
        and not t.get("review_pending")
    )
    if mm_open >= 1:
        return await interaction.followup.send(
            "❌ You already have an open middleman ticket. Please close it before opening a new one.",
            ephemeral=True
        )

    counter_doc = await get_doc(counters_col, "counters") or {"i2c": 0, "c2i": 0, "c2c": 0}
    counter_doc["mm"] = counter_doc.get("mm", 0) + 1
    ticket_number = counter_doc["mm"]
    await set_doc(counters_col, "counters", counter_doc)

    channel_name = f"🎟┃mm-{ticket_number}"
    guild = interaction.guild
    cat = guild.get_channel(MM_CATEGORY_ID)
    if not cat:
        cat = discord.utils.get(guild.categories, name="MIDDLEMAN") or await guild.create_category("MIDDLEMAN")

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user:   discord.PermissionOverwrite(view_channel=True, send_messages=True),
        guild.me:           discord.PermissionOverwrite(view_channel=True, send_messages=True),
    }
    channel = await guild.create_text_channel(channel_name, category=cat, overwrites=overwrites)

    await set_doc(tickets_col, str(channel.id), {
        "client": interaction.user.id, "exchanger": None,
        "amount": amt, "asset": mm_type, "type": "mm",
        "ticket_number": ticket_number, "vouch_pending": False,
        "other_party": other_party, "details": details
    })

    mm_role   = guild.get_role(MM_ROLE_ID)
    ping_text = f"{interaction.user.mention} {mm_role.mention}" if mm_role else interaction.user.mention
    await channel.send(content=ping_text)

    amt_float    = clean_float(amt)
    type_display = "INR Middleman" if mm_type == "inr" else "Crypto Middleman"
    amt_display  = f"₹{amt_float:g}" if mm_type == "inr" else f"${amt_float:g}"

    embed = discord.Embed(title=f"<a:ticket:1530269895517016275> KING MIDDLEMAN • {type_display}", color=0x2b2d31)
    embed.description = (
        f"<a:griffondot:1530242376264585247> Welcome {interaction.user.mention} to **KING MIDDLEMAN SERVICE**!\n"
        f"Our staff will hold funds and ensure a cash deal for both parties.\n\n"
    )
    embed.add_field(
        name="<a:ticket:1530269895517016275> Client & Ticket ID",
        value=f"{interaction.user.mention}\n`#{ticket_number:04d}`",
        inline=True
    )
    embed.add_field(
        name="<a:arrowyellow:1530241815121232072> Amount & Type",
        value=f"`{amt_display}`\n`{type_display}`",
        inline=True
    )
    embed.add_field(
        name="<a:griffondot:1530242376264585247> Other Party",
        value=f"`{other_party}`",
        inline=True
    )
    embed.add_field(name="📝 Deal Details", value=f"```{details}```", inline=False)

    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    else:
        embed.set_thumbnail(url=interaction.user.display_avatar.url)

    embed.set_footer(text="King Exchange & MM • Middleman Service")
    await channel.send(embed=embed, view=ClaimView())
    await interaction.followup.send(f"✅ Middleman ticket created: {channel.mention}", ephemeral=True)
async def open_support_ticket(interaction: discord.Interaction, s_type: str, details: dict):
    await interaction.response.defer(ephemeral=True)

    # Check existing support tickets — max 2 at a time
    all_tickets = await get_all(tickets_col)
    support_open = sum(
        1 for t in all_tickets.values()
        if t.get("client") == interaction.user.id and str(t.get("type", "")).startswith("support_")
    )
    if support_open >= 2:
        return await interaction.followup.send(
            "❌ You already have 2 open support tickets. Please close one before opening another.",
            ephemeral=True
        )

    # Counter for support ticket numbers
    counter_doc = await get_doc(counters_col, "counters") or {"i2c": 0, "c2i": 0, "c2c": 0}
    counter_doc[s_type] = counter_doc.get(s_type, 0) + 1
    ticket_number = counter_doc[s_type]
    await set_doc(counters_col, "counters", counter_doc)

    type_info = {
        "support":   ("📩┃support",   "Support Ticket",      "SUPPORT TICKETS"),
        "report": ("🚨┃report", "Report Exchanger", "SUPPORT TICKETS"),
    }
    channel_prefix, type_display, default_cat_name = type_info.get(s_type, ("🎫┃support", "Support Ticket", "SUPPORT TICKETS"))
    channel_name = f"{channel_prefix}-{ticket_number}"
    guild        = interaction.guild

    support_cat_setting = os.getenv("SUPPORT_CATEGORY_NAME", default_cat_name)
    cat = None
    if support_cat_setting.isdigit():
        cat = guild.get_channel(int(support_cat_setting))
    if not cat:
        cat = discord.utils.get(guild.categories, name=support_cat_setting) \
              or await guild.create_category(support_cat_setting)

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user:   discord.PermissionOverwrite(view_channel=True, send_messages=True),
        guild.me:           discord.PermissionOverwrite(view_channel=True, send_messages=True),
    }
    channel = await guild.create_text_channel(channel_name, category=cat, overwrites=overwrites)

    await set_doc(tickets_col, str(channel.id), {
        "client": interaction.user.id,
        "exchanger": None,
        "amount": "0",
        "asset": s_type,
        "type": "support_help" if s_type == "support" else "support_report",
        "ticket_number": ticket_number,
        "vouch_pending": False,
        "is_support": True
    })

    # Support / Staff Role Mention
    support_role_id = int(os.getenv("SUPPORT_ROLE_ID") or 0)
    role_to_ping = guild.get_role(support_role_id) if support_role_id else None
    if not role_to_ping:
        for r_id in [I2C_ROLE_ID, C2I_ROLE_ID, C2C_ROLE_ID]:
            if r_id:
                r = guild.get_role(r_id)
                if r:
                    role_to_ping = r
                    break

    ping_text = f"{interaction.user.mention} {role_to_ping.mention}" if role_to_ping else interaction.user.mention
    await channel.send(content=ping_text)

    embed = discord.Embed(title=f"🛡️ KING SUPPORT • {type_display}", color=0x5865F2)
    embed.description = (
        f"👋 Welcome {interaction.user.mention} to **Support**!\n"
        f"Our team has been notified. A staff member will assist you shortly.\n\n"
    )
    embed.add_field(name="👤 User", value=interaction.user.mention, inline=True)
    embed.add_field(name="🎫 Ticket ID", value=f"`#{ticket_number:04d}`", inline=True)
    embed.add_field(name="⚡ Category", value=f"`{type_display}`", inline=True)

    if s_type == "support":
        embed.add_field(name="❓ Issue / Query", value=f"```{details.get('query', 'N/A')}```", inline=False)
    elif s_type == "report":
        embed.add_field(name="🚨 Reported Exchanger", value=f"`{details.get('exchanger', 'N/A')}`", inline=True)
        embed.add_field(name="📝 Reason & Details", value=f"```{details.get('reason', 'N/A')}```", inline=False)

    if guild.icon: embed.set_thumbnail(url=guild.icon.url)
    else: embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text="King Exchange & MM • Support Hub")

    await channel.send(embed=embed)
    await interaction.followup.send(f"✅ Support ticket created: {channel.mention}", ephemeral=True)
async def perform_claim(channel, user, guild):
    cid    = str(channel.id)
    ticket = await get_doc(tickets_col, cid)
    if not ticket:
        return await channel.send("❌ Ticket not found.")

    if ticket["type"] in ("support_help", "support_report"):
        return await channel.send("❌ Support tickets cannot be claimed.")

    if ticket.get("exchanger"):
        exchanger = guild.get_member(ticket["exchanger"])
        return await channel.send(
            f"❌ Already claimed by {exchanger.mention if exchanger else 'another exchanger'}."
        )

    if ticket.get("client") == user.id:
        return await channel.send("❌ You cannot claim your own ticket.")

    staff_role_ids = [I2C_ROLE_ID, C2I_ROLE_ID, C2C_ROLE_ID]
    user_role_ids  = [r.id for r in user.roles]
    has_staff_role = any(rid in user_role_ids for rid in staff_role_ids if rid != 0)
    if not has_staff_role and user.id != OWNER_ID:
        return await channel.send("❌ You don't have permission to claim tickets.")

    limit_doc    = await get_doc(limits_col, str(user.id))
    limit        = limit_doc["limit"] if limit_doc else None
    all_tickets  = await get_all(tickets_col)
    rates_doc_for_active = await get_doc(rates_col, "rates") or {}
    i2c_rate_for_active  = clean_float(rates_doc_for_active.get("i2c_rate", "99"))

    active_total = 0.0
    for t in all_tickets.values():
        if t.get("exchanger") == user.id and not t.get("vouch_pending"):
            t_amt = clean_float(t.get("amount", 0))
            if t.get("type") in ("i2c", "cash_i2c") and i2c_rate_for_active > 0:
                t_amt = round(t_amt / i2c_rate_for_active, 4)
            active_total += t_amt

    raw_amt = clean_float(ticket.get("amount", 0))
    if ticket.get("type") in ("i2c", "cash_i2c"):
        rates_doc = await get_doc(rates_col, "rates") or {}
        if ticket.get("type") == "cash_i2c":
            i2c_rate = clean_float(
                rates_doc.get(
                    "cash_i2c_rate",
                    rates_doc.get("i2c_rate", "99")
                )
            )
        else:
            i2c_rate = clean_float(
                rates_doc.get("i2c_rate", "99")
        )
        ticket_amt = round(raw_amt / i2c_rate, 4) if i2c_rate > 0 else raw_amt
    else:
        ticket_amt = raw_amt

    if limit is not None and user.id != OWNER_ID:
        if active_total + ticket_amt > limit:
            return await channel.send(
                f"❌ {user.mention} has reached their limit!\n"
                f"🔺 Limit: **{limit}$**\n"
                f"💰 Active Total: **{active_total}$** / **{limit}$**\n"
                f"🚫 Cannot claim this ticket of **{ticket_amt}$**"
            )

    ticket["exchanger"] = user.id
    ticket["claimed_at"] = datetime.now().isoformat()
    await set_doc(tickets_col, cid, ticket)

    amt_display = f"{ticket_amt}$"
    if ticket.get("type") == "cash_c2i":
        c2i_rate_val = await get_cash_c2i_rate(ticket_amt)
    elif ticket.get("type") == "c2i":
        c2i_rate_val = await get_c2i_rate(ticket_amt)
        if c2i_rate_val > 0:
            inr_equiv = int(round(ticket_amt * c2i_rate_val))
            amt_display = f"{ticket_amt}$ (≈ ₹{inr_equiv})"

    limit_display = "Unlimited" if limit is None else f"${limit}"
    new_active_total = round(active_total + ticket_amt, 4)
    claimed_embed = discord.Embed(title="🎉 Ticket Claimed", color=0x57F287)
    claimed_embed.description = (
        f"Greetings! {user.mention} is now handling this ticket.\n\n"
        f"• **Exchanger's Limit:** `{limit_display}`\n"
        f"• **Claim Amount:** `{amt_display}`\n"
        f"• **Active Total:** `${new_active_total}` / `{limit_display}`\n\n"
        "🔺 *Please follow all guidelines and remain respectful and patient.*"
    )
    claimed_embed.set_footer(text="King Exchange & MM • Fast, Secure & Trusted")
    await channel.send(embed=claimed_embed)

    type_emoji = {"i2c": "🎫", "c2i": "💵", "c2c": "🏦", "support_help": "📩", "support_report": "🚨"}
    emoji      = type_emoji.get(ticket["type"], "🎫")
    try:
        await channel.edit(name=f"{emoji}┃claimed-by-{user.name}")
    except discord.HTTPException:
        pass

    return True

@bot.command(name="claim", aliases=["c"])
@check_staff()
async def claim(ctx):
    await perform_claim(ctx.channel, ctx.author, ctx.guild)
# ═══════════════════════════════════════════════════════════════════════════════
#  VIEWS
# ═══════════════════════════════════════════════════════════════════════════════

class ClaimView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim Ticket", style=discord.ButtonStyle.green, custom_id="claim_btn")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        cid    = str(interaction.channel.id)
        ticket = await get_doc(tickets_col, cid)

        if not ticket:
            return await interaction.response.send_message("❌ Ticket not found.", ephemeral=True)
        if ticket["type"] in ("support_help", "support_report"):
            return await interaction.response.send_message("❌ Support tickets cannot be claimed.", ephemeral=True)
        if ticket.get("exchanger"):
            exchanger = interaction.guild.get_member(ticket["exchanger"])
            return await interaction.response.send_message(
                f"❌ Already claimed by {exchanger.mention if exchanger else 'another exchanger'}.", ephemeral=True)
        if ticket.get("client") == interaction.user.id:
            return await interaction.response.send_message("❌ You cannot claim your own ticket.", ephemeral=True)

        await interaction.response.send_message("✅ Ticket claimed.", ephemeral=True)

        result = await perform_claim(interaction.channel, interaction.user, interaction.guild)
        if result:
            button.disabled = True
            button.label    = f"Claimed by {interaction.user.name}"
            if interaction.message:
                await interaction.message.edit(view=self)


class ExchangeSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="INR To Crypto",   description="Exchange INR to Crypto",   value="i2c", emoji="💸"),
            discord.SelectOption(label="Crypto To INR",   description="Exchange Crypto to INR",   value="c2i", emoji="💰"),
            discord.SelectOption(label="Crypto To Crypto",description="Exchange Crypto to Crypto",value="c2c", emoji="🪙"),
        ]
        super().__init__(placeholder="Start Exchange", min_values=1, max_values=1,
                         options=options, custom_id="exchange_select")

    async def callback(self, interaction: discord.Interaction):
        modal_map = {"i2c": INRToCryptoModal, "c2i": CryptoToINRModal, "c2c": CryptoToCryptoModal}
        await interaction.response.send_modal(modal_map[self.values[0]]())


class PanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ExchangeSelect())

class MMSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="INR MM",    description="Middleman for INR deals",    value="inr",    emoji="💰"),
            discord.SelectOption(label="Crypto MM", description="Middleman for Crypto deals", value="crypto", emoji="🪙"),
        ]
        super().__init__(placeholder="Select Middleman Type", min_values=1, max_values=1,
                         options=options, custom_id="mm_select")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(MMModal(self.values[0]))


class MMPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(MMSelect())
class SupportSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Support Ticket",
                description="Get support for exchange-related queries",
                value="support",
                emoji="🎫"
            ),
            discord.SelectOption(
                label="Report Exchanger",
                description="Report fraudulent or suspicious exchangers",
                value="report",
                emoji="🚨"
            ),
        ]
        super().__init__(
            placeholder="Select ticket category",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="support_select"
        )

    async def callback(self, interaction: discord.Interaction):
        modal_map = {
            "support": SupportHelpModal,
            "report": SupportReportModal,
        }
        await interaction.response.send_modal(modal_map[self.values[0]]())


class SupportPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(SupportSelect())

class CashExchangeSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Cash INR To Crypto",
                description="INR → Crypto (Min $50) — Same Rates, Extra Cash",
                value="cash_i2c",
                emoji="💸"
            ),
            discord.SelectOption(
                label="Cash Crypto To INR",
                description="Crypto → INR (Min $50) — Same Rates, Extra Cash",
                value="cash_c2i",
                emoji="💰"
            ),
        ]
        super().__init__(
            placeholder="🛡️ Open Cash Exchange Ticket",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="cash_exchange_select"
        )

    async def callback(self, interaction: discord.Interaction):
        modal_map = {"cash_i2c": CashI2CModal, "cash_c2i": CashC2IModal}
        await interaction.response.send_modal(modal_map[self.values[0]]())

class CashExchangePanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(CashExchangeSelect())



class ConfirmCloseView(discord.ui.View):
    def __init__(self, requester_id: int):
        super().__init__(timeout=None)
        self.requester_id = requester_id

    @discord.ui.button(label="✅ Confirm Close", style=discord.ButtonStyle.danger, custom_id="confirm_close")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.requester_id:
            return await interaction.response.send_message("❌ Only the person who ran `.close` can confirm this.", ephemeral=True)
        cid = str(interaction.channel.id)
        await tickets_col.delete_one({"_id": cid})
        await interaction.response.send_message("🗑️ Closing in 3 seconds...")
        await asyncio.sleep(3)
        await interaction.channel.delete()

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary, custom_id="cancel_close")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.requester_id:
            return await interaction.response.send_message("❌ Only the person who ran `.close` can cancel this.", ephemeral=True)
        await interaction.message.delete()
        await interaction.response.send_message("✅ Close cancelled.", ephemeral=True)

# ═══════════════════════════════════════════════════════════════════════════════
#  COMMANDS — ADMIN
# ═══════════════════════════════════════════════════════════════════════════════

@bot.command()
async def help(ctx):
    embed = discord.Embed(title="🛠️ King Exchange Bot | Help Menu", color=0x5865f2)
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.description = "All available commands. <a:crownyellow:1530251567880736788> = Owner only."

    embed.add_field(name="<a:crownyellow:1530251567880736788> Owner Only",
        value=(
            "`+setlimit @user [amt]` - Set exchanger limit\n"
            "`+setunlimited @user` - Remove limit (unlimited claims)\n"
            "`+ds` - Deal summary (daily/weekly/monthly/lifetime)\n"
            "`+setds <daily/weekly/monthly/lifetime> <amt>` - Set ds totals\n"
            "`+resetds <period/all>` - Clear ds override\n"
            "`+fixtickets` - Fix orphaned tickets\n"
            "`+addtrade @user [amt] [type]` - Add trade manually\n"
            "`+removetrade @user [amt]` - Remove a trade\n"
            "`+setvolume @user [amt]` - Set total volume\n"
            "`+editstats @user <client/exchanger> <deals/volume> <val>` - Edit stats\n"
            "`+resetcounters` - Reset ticket # counters\n"
            "`+set i2c/c2i/c2c [rate]` - Update exchange rates\n"
            "`+set c2i_high [rate]` - Set C2I rate for ≥$100\n"
            "`+setrate [name] [val]` - Update custom rate\n"
            "`/setup_panel` - Deploy exchange panel\n"
            "`/setup_cash_panel` - Deploy Cash Exchange panel (min $50)\n"
            "`/setup_support_panel` - Deploy support panel (`.setupsupport`)\n"
            "`/setup_mm_panel` - Deploy middleman panel (`.setupmm`)\n"
            "`+setupcash` - Deploy Cash Exchange panel (prefix)"
        ), inline=False)
        

    embed.add_field(name="💼 Staff Tools",
        value=(
            "`+vouch` - Auto-send vouch message using ticket data\n"
            "`+mvouch` / `+vouchmanual` - Manually send vouch with custom amount/type/asset\n"
            "`+mmvouch @client [amt] [inr/crypto]` - Send MM vouch message\n"
            "`+dn` - Complete trade, archive transcript & move to review (exchange/MM only)\n"
            "`+approve` - Final close after review (mod only)\n"
            "`+sclose` - Close support ticket, archive & transcript\n"
            "`+transcript` - Generate transcript to DMs\n"
            "`+claim or +c` - Claim ticket\n"
            "`+unclaim or +u` - Unclaim ticket\n"
            "`+adduser @user` - Add user to ticket\n"
            "`+removeuser @user` - Remove user from ticket\n"
            "`+close` - Close ticket without transcript\n"
            "`+ss` - Upload payment screenshot\n"
        ), inline=False)

    embed.add_field(name="📊 Stats & Info",
        value=(
            "`+stats [@user]` - View client + exchanger stats\n"
            "`+p [@user]` - Exchanger profile\n"  # tax info disabled
            "`+lb [10/20/50]` - Leaderboard by volume\n"
            "`+summary [daily/weekly]` - Summary"
        ), inline=False)

    embed.add_field(name="<a:money:1530269856308531380> Wallet Management",
        value=(
            "`+manage upi/address/id` - Manage with buttons\n"
            "`+addupi [label] [upi]` - Add UPI\n"
            "`+addaddy [label] [addr]` - Add address\n"
            "`+addid [label] [id]` - Add ID\n"
            "`+delupi/deladdy/delid [n]` - Delete by number\n"
            "`+upi [@user]` - Show all UPIs\n"
            "`+address [@user]` - Show all addresses\n"
            "`+id [@user]` - Show all IDs"
        ), inline=False)

    embed.add_field(name="⚙️ Utilities",
        value=(
            "`+mmqr [slot] [amt]` - Generate UPI QR with note\n"
            "`+upi1/.upi2` - Fetch UPI by slot\n"
            "`+usdt/.ltc/.btc/.bgmi` - Fetch by label\n"
            "`+i2c [₹]` - INR → Crypto calculator\n"
            "`+c2i [$]` - Crypto → INR calculator\n"
            "`+calc [expr]` - Math calculator\n"
            "`+pn` - Send copyable pay note\n"
            "`+vanity` - Get server invite link"
        ), inline=False)

    embed.set_footer(text="King Exchange • Ticket Bot")
    await ctx.send(embed=embed)


# @bot.command()
# @commands.has_permissions(administrator=True)
# async def set(ctx, trade_type: str, *, value: str):
#     trade_type = trade_type.lower()
#     if trade_type not in ["i2c", "c2i", "c2c"]:
#         return await ctx.send("❌ Invalid type. Use `i2c`, `c2i` or `c2c`")
#     doc = await get_doc(rates_col, "rates") or {}
#     doc[f"{trade_type}_rate"] = value
#     await set_doc(rates_col, "rates", doc)
#     await ctx.send(f"✅ {trade_type.upper()} rate updated to `{value}`")

@bot.command()
@check_owner()
async def set(ctx, trade_type: str, *, value: str):
    trade_type = trade_type.lower()
    if trade_type not in ["i2c", "c2i", "c2c", "c2i_high"]:
        return await ctx.send("❌ Invalid type. Use `i2c`, `c2i`, `c2i_high` or `c2c`")
    doc = await get_doc(rates_col, "rates") or {}
    doc[f"{trade_type}_rate"] = value
    await set_doc(rates_col, "rates", doc)
    await ctx.send(f"✅ {trade_type.upper()} rate updated to `{value}`")

@bot.command(name="cashset")
@check_owner()
async def cashset(ctx, trade_type: str, *, value: str):
    trade_type = trade_type.lower()

    mapping = {
        "i2c": "cash_i2c_rate",
        "c2i": "cash_c2i_rate",
        "c2i_high": "cash_c2i_high_rate",
    }

    if trade_type not in mapping:
        return await ctx.send(
            "❌ Invalid type. Use `i2c`, `c2i` or `c2i_high`."
        )

    doc = await get_doc(rates_col, "rates") or {}
    doc[mapping[trade_type]] = value
    await set_doc(rates_col, "rates", doc)

    await ctx.send(
        f"✅ Cash {trade_type.upper()} rate updated to `{value}`"
    )
@bot.command(name="setlimit")
async def setlimit(ctx, user: discord.Member = None, *, limit: str = None):
    if not is_owner(ctx): return await ctx.send("❌ Owner only.")
    if not user or not limit: return await ctx.send("❌ Usage: `.setlimit @user <amount>`")
    limit_val = clean_float(limit)
    if limit_val <= 0: return await ctx.send("❌ Limit must be greater than 0.")
    await set_doc(limits_col, str(user.id), {"limit": limit_val})
    await ctx.send(f"✅ Limit for {user.mention} set to `{limit_val}$`")

@bot.command(name="setunlimited")
@check_owner()
async def setunlimited(ctx, user: discord.Member = None):
    if not user:
        return await ctx.send("❌ Usage: `+setunlimited @user`")
    await limits_col.delete_one({"_id": str(user.id)})
    await ctx.send(f"✅ {user.mention} now has an **unlimited** claim limit.")

@bot.command()
@commands.has_permissions(administrator=True)
async def fixtickets(ctx):
    if not is_owner(ctx) and not ctx.author.guild_permissions.administrator:
        return await ctx.send("❌ Owner only.")
    all_tickets = await get_all(tickets_col)
    removed = 0
    for cid in list(all_tickets.keys()):
        try:
            await bot.fetch_channel(int(cid))
        except discord.NotFound:
            await tickets_col.delete_one({"_id": cid})
            removed += 1
        except Exception: pass
    await ctx.send(f"✅ Removed {removed} orphaned ticket(s).")


@bot.command()
@check_owner()
async def setrate(ctx, name, value):
    doc = await get_doc(rates_col, "rates") or {}
    doc[name] = value
    await set_doc(rates_col, "rates", doc)
    await ctx.send(f"✅ Rate `{name}` updated to `{value}`")

@bot.command(name="resetcounters")
async def resetcounters(ctx):
    if not is_owner(ctx): return await ctx.send("❌ Owner only.")
    await set_doc(counters_col, "counters", {"i2c": 0, "c2i": 0, "c2c": 0, "mm": 0})
    await ctx.send("✅ Counters reset. Next tickets will start from #1.")
# ═══════════════════════════════════════════════════════════════════════════════
#  WALLET MANAGEMENT — IMPROVED
# ═══════════════════════════════════════════════════════════════════════════════

# ── Modals for adding entries ─────────────────────────────────────────────────

class AddEntryModal(discord.ui.Modal, title="Add New Entry"):
    label_input = discord.ui.TextInput(label="Name / Label", placeholder="e.g. Phonepe Wallet / USDT / Binance")
    value_input = discord.ui.TextInput(label="Value", placeholder="e.g. 1234567890@upi / 0x4b236...", style=discord.TextStyle.paragraph)

    def __init__(self, category: str):
        super().__init__()
        self.category = category

    async def on_submit(self, interaction: discord.Interaction):
        uid  = str(interaction.user.id)
        doc  = await get_doc(wallets_col, uid) or {}
        key_map = {"upi": "upis", "address": "addys", "id": "ids"}
        key  = key_map[self.category]
        items = doc.get(key, [])
        if len(items) >= 10:
            return await interaction.response.send_message("❌ Maximum 10 entries allowed.", ephemeral=True)
        items.append({"label": self.label_input.value, "value": self.value_input.value})
        doc[key] = items
        await set_doc(wallets_col, uid, doc)
        await interaction.response.send_message(f"✅ Added `{self.label_input.value}` as #{len(items)}", ephemeral=True)


class DeleteEntrySelect(discord.ui.Select):
    def __init__(self, category: str, items: list):
        self.category = category
        options = [
            discord.SelectOption(
                label=f"{i+1}. {item['label'] if isinstance(item, dict) else 'Entry'}",
                value=str(i)
            )
            for i, item in enumerate(items)
        ]
        super().__init__(placeholder="Select entry to delete", options=options, custom_id=f"del_{category}")

    async def callback(self, interaction: discord.Interaction):
        uid     = str(interaction.user.id)
        doc     = await get_doc(wallets_col, uid) or {}
        key_map = {"upi": "upis", "address": "addys", "id": "ids"}
        key     = key_map[self.category]
        items   = doc.get(key, [])
        idx     = int(self.values[0])
        if idx < len(items):
            removed = items.pop(idx)
            doc[key] = items
            await set_doc(wallets_col, uid, doc)
            # Handle both old string format and new dict format
            label = removed["label"] if isinstance(removed, dict) else removed
            await interaction.response.send_message(f"✅ Deleted `{label}`", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Entry not found.", ephemeral=True)


class DeleteEntryView(discord.ui.View):
    def __init__(self, category: str, items: list):
        super().__init__(timeout=30)
        self.add_item(DeleteEntrySelect(category, items))


class ManageView(discord.ui.View):
    def __init__(self, category: str):
        super().__init__(timeout=60)
        self.category = category

    @discord.ui.button(label=". Add", style=discord.ButtonStyle.green, custom_id="manage_add")
    async def add(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AddEntryModal(self.category))

    @discord.ui.button(label="- Delete", style=discord.ButtonStyle.danger, custom_id="manage_delete")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid     = str(interaction.user.id)
        doc     = await get_doc(wallets_col, uid) or {}
        key_map = {"upi": "upis", "address": "addys", "id": "ids"}
        items   = doc.get(key_map[self.category], [])
        if not items:
            return await interaction.response.send_message("❌ Nothing to delete.", ephemeral=True)
        await interaction.response.send_message(
            "Select entry to delete:", view=DeleteEntryView(self.category, items), ephemeral=True)


@bot.command(name="manage")
@check_staff()
async def manage(ctx, category: str = None):
    if not category or category.lower() not in ["upi", "address", "id"]:
        return await ctx.send("❌ Usage: `.manage upi` / `.manage address` / `.manage id`")
    category = category.lower()
    key_map  = {"upi": "upis", "address": "addys", "id": "ids"}
    title_map = {"upi": "Manage UPI IDs", "address": "Manage Crypto Addresses", "id": "Manage IDs"}
    btn_map  = {"upi": ("+ Add UPI ID", "- Delete UPI ID"),
                "address": ("+ Add Address", "- Delete Address"),
                "id": ("+ Add ID", "- Delete ID")}
    key      = key_map[category]
    doc      = await get_doc(wallets_col, str(ctx.author.id)) or {}
    items    = doc.get(key, [])

    embed = discord.Embed(title=title_map[category], color=0x2b2d31)
    if items:
        for i, item in enumerate(items):
            # Handle both old format (string) and new format (dict)
            if isinstance(item, str):
                embed.add_field(name=f"{i+1}. Entry", value=f"`{item}`", inline=False)
            else:
                embed.add_field(name=f"{i+1}. {item['label']}", value=f"`{item['value']}`", inline=False)
    else:
        embed.description = "No entries saved yet."
    embed.set_footer(text=f"Maximum 10 entries allowed.")

    view = ManageView(category)
    # Rename buttons based on category
    view.children[0].label = btn_map[category][0]
    view.children[1].label = btn_map[category][1]
    await ctx.send(embed=embed, view=view)


# ── FETCH commands ────────────────────────────────────────────────────────────

@bot.command(name="upi")
@check_staff()
async def upi(ctx, slot_or_user: str = None, user: discord.Member = None):
    target = user or ctx.author
    slot   = None

    if slot_or_user:
        if slot_or_user.isdigit():
            slot = int(slot_or_user)
        else:
            try: target = await commands.MemberConverter().convert(ctx, slot_or_user)
            except Exception: pass

    doc   = await get_doc(wallets_col, str(target.id)) or {}
    items = [normalize_wallet_item(i) for i in doc.get("upis", [])]
    if not items: return await ctx.send(f"**{target.name}** has no UPIs saved.")

    if slot:
        if slot < 1 or slot > len(items):
            return await ctx.send(f"❌ {target.name} has {len(items)} UPI(s).")
        item = items[slot - 1]
        await ctx.send(f"**{target.name}'s UPI #{slot} ({item['label']}):** `{item['value']}`")
    else:
       lines = "\n".join([f"**{i+1}. {item['label']}** — `{item['value']}`" for i, item in enumerate(items)])
       await ctx.send(f"**{target.name}'s UPIs:**\n{lines}")


@bot.command(name="address", aliases=["addy"])
@check_staff()
async def addy(ctx, slot_or_user: str = None, user: discord.Member = None):
    target = user or ctx.author
    slot   = None

    if slot_or_user:
        if slot_or_user.isdigit():
            slot = int(slot_or_user)
        else:
            try: target = await commands.MemberConverter().convert(ctx, slot_or_user)
            except Exception: pass

    doc   = await get_doc(wallets_col, str(target.id)) or {}
    items = [normalize_wallet_item(i) for i in doc.get("addys", [])]
    if not items: return await ctx.send(f"**{target.name}** has no addresses saved.")

    if slot:
        if slot < 1 or slot > len(items):
            return await ctx.send(f"❌ {target.name} has {len(items)} address(es).")
        item = items[slot - 1]
        await ctx.send(f"**{target.name}'s Address #{slot} ({item['label']}):**\n```{item['value']}```")
    else:
        lines = "\n".join([f"**{i+1}. {item['label']}** — `{item['value']}`" for i, item in enumerate(items)])
        await ctx.send(f"**{target.name}'s Addresses:**\n{lines}")


# ── MMQR with payment note ────────────────────────────────────────────────────

@bot.command(name="mmqr")
@check_staff()
async def mmqr(ctx, slot: str = None, amount: str = None):
    doc   = await get_doc(wallets_col, str(ctx.author.id)) or {}
    items = [normalize_wallet_item(i) for i in doc.get("upis", [])]
    if not items: return await ctx.send("❌ No UPIs saved. Use `.manage upi` first.")

    if slot and slot.isdigit():
        idx = int(slot) - 1
        if idx < 0 or idx >= len(items):
            return await ctx.send(f"❌ You have {len(items)} UPI(s).")
        upi_item = items[idx]
    else:
        upi_item = items[0]
        amount   = slot

    upi_id   = upi_item["value"]
    upi_data = f"upi://pay?pa={upi_id}"
    if amount:
        amt_val = clean_float(amount)
        if amt_val > 0:
            upi_data += f"&am={amt_val}"
    # Add payment note
    upi_data += "&tn=I%20have%20authorised%20this%20payment%20and%20got%20the%20product"

    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={urllib.parse.quote(upi_data)}"
    embed  = discord.Embed(
        title=f"📱 {upi_item['label']}",
        description=f"`{upi_id}`",
        color=0x5865f2
    )
    if amount:
        embed.add_field(name="Amount", value=f"₹{clean_float(amount)}")
    embed.add_field(name="Payment Note", value="I have authorised this payment and got the product", inline=False)
    embed.set_image(url=qr_url)
    await ctx.send(embed=embed)


@bot.command(name="qr")
@check_staff()   # or @check_admin() if you want only admins
async def qr(ctx, upi_id: str = None, amount: str = None):
    if not upi_id:
        return await ctx.send(
            "❌ Usage: `+qr <upi_id> [amount]`\n"
            "Example:\n"
            "`+qr merchant@ybl 500`\n"
            "`+qr 9876543210@ibl`"
        )

    upi_data = f"upi://pay?pa={upi_id}"

    amt = None
    if amount:
        try:
            amt = clean_float(amount)
            if amt > 0:
                upi_data += f"&am={amt}"
        except:
            pass

    # Payment note
    upi_data += "&tn=I%20have%20authorised%20this%20payment%20and%20got%20the%20product"

    qr_url = (
        "https://api.qrserver.com/v1/create-qr-code/"
        f"?size=400x400&data={urllib.parse.quote(upi_data)}"
    )

    embed = discord.Embed(
        title="📱 UPI Payment QR",
        color=discord.Color.green()
    )

    embed.add_field(
        name="UPI ID",
        value=f"`{upi_id}`",
        inline=False
    )

    if amt:
        embed.add_field(
            name="Amount",
            value=f"₹{amt}",
            inline=True
        )

    embed.add_field(
        name="Payment Note",
        value="I have authorised this payment and got the product.",
        inline=False
    )

    embed.set_image(url=qr_url)

    await ctx.send(embed=embed)

@bot.command(name="pn")
@check_staff()
async def paynote(ctx):
    note = "I have authorised this payment and got the product."
    await ctx.send(f"`{note}`")
# ── ADD/DEL shortcut commands (kept for compatibility) ────────────────────────
@bot.command(name="vanity")
async def vanity(ctx):
    await ctx.send("<a:announce:1530601305243127889> 𝐁𝐄𝐒𝐓 𝐄𝐗𝐂𝐇𝐀𝐍𝐆𝐄 𝐀𝐓 https://discord.gg/king-exchange <a:crown:1530229038139052052>")
@bot.command(name="addupi")
@check_staff()
async def addupi(ctx, label: str = None, *, value: str = None):
    if not label or not value:
        return await ctx.send("❌ Usage: `+addupi <label> <upi_id>`\nExample: `.addupi Phonepe 1234567890@phonepe`")
    doc   = await get_doc(wallets_col, str(ctx.author.id)) or {}
    items = doc.get("upis", [])
    if len(items) >= 10: return await ctx.send("❌ Max 10 UPIs.")
    items.append({"label": label, "value": value})
    doc["upis"] = items
    await set_doc(wallets_col, str(ctx.author.id), doc)
    await ctx.send(f"✅ UPI `{label}` saved as #{len(items)}")


@bot.command(name="addaddy")
@check_staff()
async def addaddy(ctx, label: str = None, *, value: str = None):
    if not label or not value:
        return await ctx.send("❌ Usage: `+addaddy <label> <address>`\nExample: `.addaddy USDT 0x4b236...`")
    doc   = await get_doc(wallets_col, str(ctx.author.id)) or {}
    items = doc.get("addys", [])
    if len(items) >= 10: return await ctx.send("❌ Max 10 addresses.")
    items.append({"label": label, "value": value})
    doc["addys"] = items
    await set_doc(wallets_col, str(ctx.author.id), doc)
    await ctx.send(f"✅ Address `{label}` saved as #{len(items)}")


@bot.command(name="addid")
@check_staff()
async def addid(ctx, label: str = None, *, value: str = None):
    if not label or not value:
        return await ctx.send("❌ Usage: `+addid <label> <id>`\nExample: `.addid Binance 123456`")
    doc   = await get_doc(wallets_col, str(ctx.author.id)) or {}
    items = doc.get("ids", [])
    if len(items) >= 10: return await ctx.send("❌ Max 10 IDs.")
    items.append({"label": label, "value": value})
    doc["ids"] = items
    await set_doc(wallets_col, str(ctx.author.id), doc)
    await ctx.send(f"✅ ID `{label}` saved as #{len(items)}")


@bot.command(name="delupi")
@check_staff()
async def delupi(ctx, number: int = None):
    if not number: return await ctx.send("❌ Usage: `.delupi <number>`")
    doc   = await get_doc(wallets_col, str(ctx.author.id)) or {}
    items = doc.get("upis", [])
    if number < 1 or number > len(items): return await ctx.send(f"❌ You have {len(items)} UPI(s).")
    removed = items.pop(number - 1)
    doc["upis"] = items
    await set_doc(wallets_col, str(ctx.author.id), doc)
    label = removed["label"] if isinstance(removed, dict) else removed
    await ctx.send(f"✅ UPI `{label}` deleted.")


@bot.command(name="deladdy")
@check_staff()
async def deladdy(ctx, number: int = None):
    if not number: return await ctx.send("❌ Usage: `.deladdy <number>`")
    doc   = await get_doc(wallets_col, str(ctx.author.id)) or {}
    items = doc.get("addys", [])
    if number < 1 or number > len(items): return await ctx.send(f"❌ You have {len(items)} address(es).")
    removed = items.pop(number - 1)
    doc["addys"] = items
    await set_doc(wallets_col, str(ctx.author.id), doc)
    label = removed["label"] if isinstance(removed, dict) else removed
    await ctx.send(f"✅ Address `{label}` deleted.")


@bot.command(name="delid")
@check_staff()
async def delid(ctx, number: int = None):
    if not number: return await ctx.send("❌ Usage: `.delid <number>`")
    doc   = await get_doc(wallets_col, str(ctx.author.id)) or {}
    items = doc.get("ids", [])
    if number < 1 or number > len(items): return await ctx.send(f"❌ You have {len(items)} ID(s).")
    removed = items.pop(number - 1)
    doc["ids"] = items
    await set_doc(wallets_col, str(ctx.author.id), doc)
    label = removed["label"] if isinstance(removed, dict) else removed
    await ctx.send(f"✅ ID `{label}` deleted.")

@bot.command(name="id")
@check_staff()
async def id_cmd(ctx, slot_or_user: str = None, user: discord.Member = None):
    target = user or ctx.author
    slot   = None
    if slot_or_user:
        if slot_or_user.isdigit():
            slot = int(slot_or_user)
        else:
            try: target = await commands.MemberConverter().convert(ctx, slot_or_user)
            except Exception: pass
    doc   = await get_doc(wallets_col, str(target.id)) or {}
    items = [normalize_wallet_item(i) for i in doc.get("ids", [])]
    if not items: return await ctx.send(f"**{target.name}** has no IDs saved.")
    if slot:
        if slot < 1 or slot > len(items):
            return await ctx.send(f"❌ {target.name} has {len(items)} ID(s).")
        item = items[slot - 1]
        await ctx.send(f"**{target.name}'s ID #{slot} ({item['label']}):** `{item['value']}`")
    else:
        lines = "\n".join([f"**{i+1}. {item['label']}** — `{item['value']}`" for i, item in enumerate(items)])
        await ctx.send(f"**{target.name}'s IDs:**\n{lines}")
# ═══════════════════════════════════════════════════════════════════════════════
#  COMMANDS — UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

@bot.command()
async def calc(ctx, *, expression: str = None):
    if not expression: return await ctx.send("❌ Usage: `.calc 100 * 95`")
    try:
        safe   = "".join(c for c in expression if c in "0123456789.+-*/() ")
        result = eval(safe)
        result = round(result, 1)

        embed = discord.Embed(title="KING EXCHANGE & MM", color=0x5865f2)
        embed.description = "Calculation Result"
        embed.add_field(name="Expression", value=f"`{safe.strip()}`", inline=False)
        embed.add_field(name="Result",     value=f"`{result:g}`",     inline=False)
        embed.set_footer(text=f"Calculated for {ctx.author.display_name}")
        await ctx.send(embed=embed)
    except Exception:
        await ctx.send("❌ Invalid expression.")


@bot.command(name="i2c")
async def i2c_calc(ctx, amount: str = None):
    if not amount: return await ctx.send("❌ Usage: `.i2c <amount in ₹>`")
    amt    = clean_float(amount)
    rates  = await get_doc(rates_col, "rates") or {}
    rate   = clean_float(rates.get("i2c_rate", "99"))
    if rate <= 0: return await ctx.send("❌ Rate not set.")
    result = round(amt / rate, 2)

    embed = discord.Embed(title="KING EXCHANGE & MM", color=0x2b2d31)
    embed.description = "💸 INR to Crypto Conversion"
    if ctx.guild.icon:
        embed.set_thumbnail(url=ctx.guild.icon.url)
    embed.add_field(name="Client Will Pay",    value=f"`₹{amt:.2f}`",   inline=False)
    embed.add_field(name="I2C Rate",           value=f"`₹{rate:.2f}/$`", inline=False)
    embed.add_field(name="Client Will Receive",value=f"`${result}`",    inline=False)
    embed.set_footer(text=f"Live rates • {datetime.now().strftime('%I:%M:%S %p')}")
    await ctx.send(embed=embed)


# @bot.command(name="c2i")
# async def c2i_calc(ctx, amount: str = None):
#     if not amount: return await ctx.send("❌ Usage: `+c2i <amount in $>`")
#     amt    = clean_float(amount)
#     rates  = await get_doc(rates_col, "rates") or {}
#     rate   = clean_float(rates.get("c2i_rate", "95"))
#     if rate <= 0: return await ctx.send("❌ Rate not set.")
#     result = round(amt * rate, 2)

#     embed = discord.Embed(title="PRIME EXCHANGE & MM", color=0x2b2d31)
#     embed.description = "🪙 Crypto to INR Conversion"
#     if ctx.guild.icon:
#         embed.set_thumbnail(url=ctx.guild.icon.url)
#     embed.add_field(name="Client Will Pay",    value=f"`${amt:.2f}`",    inline=False)
#     embed.add_field(name="C2I Rate",           value=f"`₹{rate:.2f}/$`", inline=False)
#     embed.add_field(name="Client Will Receive",value=f"`₹{result}`",    inline=False)
#     embed.set_footer(text=f"Live rates • {datetime.now().strftime('%I:%M:%S %p')}")
#     await ctx.send(embed=embed)

@bot.command(name="c2i")
async def c2i_calc(ctx, amount: str = None):
    if not amount: return await ctx.send("❌ Usage: `.c2i <amount in $>`")
    amt    = clean_float(amount)
    rates  = await get_doc(rates_col, "rates") or {}
    rate_low  = clean_float(rates.get("c2i_rate", "95"))
    rate_high = clean_float(rates.get("c2i_high_rate", rate_low))
    rate   = rate_high if amt >= 100 else rate_low
    if rate <= 0: return await ctx.send("❌ Rate not set.")
    result = round(amt * rate, 2)

    embed = discord.Embed(title="KING EXCHANGE & MM", color=0x2b2d31)
    embed.description = "🪙 Crypto to INR Conversion"
    if ctx.guild.icon:
        embed.set_thumbnail(url=ctx.guild.icon.url)
    embed.add_field(name="Client Will Pay",    value=f"`${amt:.2f}`",    inline=False)
    embed.add_field(name="C2I Rate",           value=f"`₹{rate:.2f}/$ ({'≥$100' if amt >= 100 else '<$100'})`", inline=False)
    embed.add_field(name="Client Will Receive",value=f"`₹{result}`",    inline=False)
    embed.set_footer(text=f"Live rates • {datetime.now().strftime('%I:%M:%S %p')}")
    await ctx.send(embed=embed)

@bot.command(name="editstats")
async def editstats(ctx, user: discord.Member = None, stat_type: str = None, field: str = None, *, value: str = None):
    if not is_owner(ctx): return await ctx.send("❌ Owner only.")
    if not all([user, stat_type, field, value]):
        return await ctx.send(
            "❌ Usage:\n"
            "`.editstats @user client deals <number>`\n"
            "`.editstats @user client volume <amount>`\n"
            "`.editstats @user exchanger deals <number>`\n"
            "`.editstats @user exchanger volume <amount>`"
        )

    stat_type = stat_type.lower()
    field = field.lower()

    if stat_type == "client":
        doc = await get_doc(client_stats_col, str(user.id)) or {"deals": 0, "volume": 0.0}
        if field == "deals":
            doc["deals"] = int(clean_float(value))
        elif field == "volume":
            doc["volume"] = round(clean_float(value), 4)
        else:
            return await ctx.send("❌ Field must be `deals` or `volume`")
        await set_doc(client_stats_col, str(user.id), doc)
        await ctx.send(f"✅ {user.mention} client `{field}` set to `{value}`")

    elif stat_type == "exchanger":
        doc = await get_doc(stats_col, str(user.id)) or {"trades": []}
        if field == "deals":
            # Adjust number of trade entries
            target = int(clean_float(value))
            current = len(doc["trades"])
            if target > current:
                # Add dummy trades to match count
                for _ in range(target - current):
                    doc["trades"].append({
                        "time": datetime.now().isoformat(),
                        "amount": 0.0,
                        "type": "manual"
                    })
            else:
                # Trim trades to match count
                doc["trades"] = doc["trades"][:target]
        elif field == "volume":
            target_vol = clean_float(value)
            # Clear all trades and add single trade with full amount
            doc["trades"] = [{
                "time": datetime.now().isoformat(),
                "amount": round(target_vol, 4),
                "type": "manual"
            }]
        else:
            return await ctx.send("❌ Field must be `deals` or `volume`")
        await set_doc(stats_col, str(user.id), doc)
        await ctx.send(f"✅ {user.mention} exchanger `{field}` set to `{value}`")

    else:
        await ctx.send("❌ Type must be `client` or `exchanger`")
# ═══════════════════════════════════════════════════════════════════════════════
#  COMMANDS — VOUCH
# ═══════════════════════════════════════════════════════════════════════════════

@bot.command(name="vouch")
@check_staff()
async def vouch(ctx):
    cid    = str(ctx.channel.id)
    ticket = await get_doc(tickets_col, cid)

    if not ticket:
        return await ctx.send("❌ Not a ticket channel.")
    if ticket.get("is_support"):
        return await ctx.send("❌ Support tickets can't be vouched.")
    if ticket.get("type") not in ("i2c", "c2i", "c2c", "cash_i2c", "cash_c2i"):
        return await ctx.send("❌ This isn't an exchange ticket. Use `+mmvouch` for middleman tickets.")
    if not ticket.get("exchanger"):
        return await ctx.send("❌ This ticket hasn't been claimed yet.")
    if ctx.author.id != ticket["exchanger"] and not is_owner(ctx):
        return await ctx.send("❌ Only the exchanger who claimed this ticket can vouch it.")

    client = ctx.guild.get_member(ticket["client"])
    if not client:
        return await ctx.send("❌ Could not find the client in this server.")

    trade_type = ticket["type"]
    amount     = ticket["amount"]
    asset      = ticket["asset"]
    amt_clean  = clean_float(amount)

    # Normalize safe types to their base type for stats/labels
    base_type = trade_type.replace("cash_", "") if trade_type.startswith("cash_") else trade_type

    # Normalize i2c (INR) amounts to USD equivalent for stats
    stats_amt = amt_clean
    if base_type == "i2c":
        rates_doc_i2c = await get_doc(rates_col, "rates") or {}
        i2c_rate_v    = clean_float(rates_doc_i2c.get("i2c_rate", "99"))
        stats_amt     = round(amt_clean / i2c_rate_v, 4) if i2c_rate_v > 0 else amt_clean

    if base_type == "c2c":
        parts = asset.upper().split("→") if "→" in asset else asset.upper().split(" ")
        trade_label = f"{parts[0].strip()} TO {parts[1].strip()}" if len(parts) == 2 else asset.upper()
    elif base_type == "i2c":
        trade_label = f"UPI TO {asset.upper()}"
    else:
        trade_label = f"{asset.upper()} TO UPI"

    vouch_channel = ctx.guild.get_channel(VOUCH_CHANNEL_ID)
    vouch_mention = vouch_channel.mention if vouch_channel else "#vouch"
    currency_symbol = "₹" if base_type == "i2c" else "$"
    rep_line      = f"+rep <@{ctx.author.id}> **EXCHANGED {trade_label} [{currency_symbol}{amt_clean}]**"

    embed = discord.Embed(color=0x2b2d31)
    embed.description = (
        f"💝 **THANK YOU!** 💝\n\nTHANK YOU FOR USING OUR SERVICE!\n"
        f"WE HOPE YOU LIKED OUR EXCHANGE EXPERIENCE.\n\n"
        f"COPY THE LINE BELOW AND PASTE IT IN {vouch_mention} TO VOUCH 🏷️\n\n"
        f"```{rep_line}```"
    )
    await ctx.send(embed=embed)
    await ctx.send(rep_line)
    await ctx.send(f"{client.mention}, PLEASE VOUCH IN {vouch_mention} OR YOU MAY BE BLACKLISTED 🚫")

    await update_stats(ctx.author.id, stats_amt, base_type)
    await send_exchange_history(ctx, client, base_type, amt_clean, asset)

    client_uid = str(ticket["client"])
    client_doc = await get_doc(client_stats_col, client_uid)
    if client_doc is None:
        client_doc = {"deals": 0, "volume": 0.0}
    client_doc["deals"] = int(client_doc.get("deals", 0)) + 1
    client_doc["volume"] = round(float(client_doc.get("volume", 0.0)) + float(stats_amt), 4)
    await set_doc(client_stats_col, client_uid, client_doc)

    client_name = client.name
    vouch_cat = None
    if str(VOUCH_PENDING_CATEGORY).isdigit():
        vouch_cat = ctx.guild.get_channel(int(VOUCH_PENDING_CATEGORY))
    if not vouch_cat:
        vouch_cat = discord.utils.get(ctx.guild.categories, name=str(VOUCH_PENDING_CATEGORY))
    if not vouch_cat:
        vouch_cat = await ctx.guild.create_category(str(VOUCH_PENDING_CATEGORY))
    ticket["vouch_pending"] = True
    await set_doc(tickets_col, cid, ticket)
    try:
        await ctx.channel.edit(category=vouch_cat)
    except Exception:
        pass
    try:
        await ctx.channel.edit(name=f"💐┃vouch-{client_name}")
    except discord.HTTPException:
        pass

@bot.command(name="mvouch", aliases=["vouchmanual"])
@check_staff()
async def mvouch(ctx, client: str = None, amount: str = None,
                  trade_type: str = None, *, asset: str = None):
    if client:
        try:
            client = await commands.MemberConverter().convert(ctx, client)
        except Exception:
            try:
                client_id = int(''.join(filter(str.isdigit, client)))
                client = ctx.guild.get_member(client_id)
            except Exception:
                return await ctx.send("❌ Could not find that user. Please mention them properly with @.")
    if not all([client, amount, trade_type, asset]):
        return await ctx.send(
            "❌ Usage: `+mvouch @client <amount> <type> <asset>`\n"
            "Examples: `+mvouch @john 30 c2i USDT` | `+mvouch @john 500 i2c LTC` | `+mvouch @john 50 c2c BTC→USDT`")
    trade_type = trade_type.lower()
    if trade_type not in ["i2c", "c2i", "c2c", "cash_i2c", "cash_c2i"]:
        return await ctx.send("❌ Invalid type. Use `i2c`, `c2i`, `c2c`, `cash_i2c` or `cash_c2i`")

    cid    = str(ctx.channel.id)
    ticket = await get_doc(tickets_col, cid)

    amt_clean = clean_float(amount)

    stats_amt = amt_clean
    # Normalize safe types for stats
    base_type = trade_type.replace("cash_", "") if trade_type.startswith("cash_") else trade_type
    if base_type == "i2c":
        rates_doc_i2c = await get_doc(rates_col, "rates") or {}
        i2c_rate_v    = clean_float(rates_doc_i2c.get("i2c_rate", "99"))
        stats_amt     = round(amt_clean / i2c_rate_v, 4) if i2c_rate_v > 0 else amt_clean

    if base_type == "c2c":
        parts = asset.upper().split("→") if "→" in asset else asset.upper().split(" ")
        trade_label = f"{parts[0].strip()} TO {parts[1].strip()}" if len(parts) == 2 else asset.upper()
    elif base_type == "i2c":
        trade_label = f"UPI TO {asset.upper()}"
    else:
        trade_label = f"{asset.upper()} TO UPI"

    currency_symbol = "₹" if base_type == "i2c" else "$"

    vouch_channel = ctx.guild.get_channel(VOUCH_CHANNEL_ID)
    vouch_mention = vouch_channel.mention if vouch_channel else "#vouch"
    rep_line      = f"+rep <@{ctx.author.id}> **EXCHANGED {trade_label} [{currency_symbol}{amt_clean}]**"

    embed = discord.Embed(color=0x2b2d31)
    embed.description = (
        f"💝 **THANK YOU!** 💝\n\nTHANK YOU FOR USING OUR SERVICE!\n"
        f"WE HOPE YOU LIKED OUR EXCHANGE EXPERIENCE.\n\n"
        f"COPY THE LINE BELOW AND PASTE IT IN {vouch_mention} TO VOUCH 🏷️\n\n"
        f"```{rep_line}```"
    )
    await ctx.send(embed=embed)
    await ctx.send(rep_line)
    await ctx.send(f"{client.mention}, PLEASE VOUCH IN {vouch_mention} OR YOU MAY BE BLACKLISTED 🚫")

    await update_stats(ctx.author.id, stats_amt, base_type)
    await send_exchange_history(ctx, client, base_type, amt_clean, asset)

    client_uid = str(client.id)
    client_doc = await get_doc(client_stats_col, client_uid)
    if client_doc is None:
        client_doc = {"deals": 0, "volume": 0.0}
    client_doc["deals"] = int(client_doc.get("deals", 0)) + 1
    client_doc["volume"] = round(float(client_doc.get("volume", 0.0)) + float(stats_amt), 4)
    await set_doc(client_stats_col, client_uid, client_doc)

    if ticket:
        vouch_cat = None
        if str(VOUCH_PENDING_CATEGORY).isdigit():
            vouch_cat = ctx.guild.get_channel(int(VOUCH_PENDING_CATEGORY))
        if not vouch_cat:
            vouch_cat = discord.utils.get(ctx.guild.categories, name=str(VOUCH_PENDING_CATEGORY))
        if not vouch_cat:
            vouch_cat = await ctx.guild.create_category(str(VOUCH_PENDING_CATEGORY))
        ticket["vouch_pending"] = True
        await set_doc(tickets_col, cid, ticket)
        try:
            await ctx.channel.edit(category=vouch_cat)
        except Exception:
            pass
        try:
            await ctx.channel.edit(name=f"💐┃vouch-{client.name}")
        except discord.HTTPException:
            pass
@bot.command(name="fixhistory")
@check_owner()
async def fixhistory(ctx, client: discord.Member, exchanger: discord.Member, ticket_number: int, trade_type: str, amount: str, *, asset: str):
    trade_type = trade_type.lower()
    if trade_type not in ["i2c", "c2i", "c2c"]:
        return await ctx.send("❌ Invalid type. Use `i2c`, `c2i` or `c2c`")
    amt_clean = clean_float(amount)

    history_channel = ctx.guild.get_channel(EXCHANGE_HISTORY_CHANNEL_ID)
    if not history_channel:
        return await ctx.send("❌ Exchange history channel not found.")

    deal_id = f"#{ticket_number:04d}"

    type_display_map = {"i2c": "INR To Crypto", "c2i": "Crypto To INR", "c2c": "Crypto To Crypto"}
    type_display = type_display_map.get(trade_type, trade_type.upper())

    rates_doc = await get_doc(rates_col, "rates") or {}

    if trade_type == "i2c":
        rate = clean_float(rates_doc.get("i2c_rate", "99"))
        crypto_amt = round(amt_clean / rate, 2) if rate > 0 else 0
        send_display    = f"₹{amt_clean:,.2f}"
        receive_display = f"{crypto_amt:,.2f} {asset.upper()}"
    elif trade_type in ("c2i", "cash_c2i"):
        if trade_type == "cash_c2i":
            rate = await get_cash_c2i_rate(amt_clean)
        else:
            rate = await get_c2i_rate(amt_clean)

        inr_amt = round(amt_clean * rate, 2) if rate > 0 else 0
        send_display    = f"{amt_clean:,.2f} {asset.upper()}"
        receive_display = f"₹{inr_amt:,.2f}"
    else:
        parts = asset.upper().split("→") if "→" in asset else asset.upper().split(" ")
        send_asset    = parts[0].strip() if len(parts) > 0 else asset.upper()
        receive_asset = parts[1].strip() if len(parts) > 1 else asset.upper()
        fee_pct  = clean_float(rates_doc.get("c2c_rate", "3"))
        recv_amt = round(amt_clean * (1 - fee_pct / 100), 2)
        send_display    = f"{amt_clean:,.2f} {send_asset}"
        receive_display = f"{recv_amt:,.2f} {receive_asset}"

    embed = discord.Embed(color=0x2b2d31)
    embed.description = "<a:check:1530250663206977701> **Deal Verified**"
    embed.add_field(name="<a:ticket:1530269895517016275> Deal ID", value=f"`{deal_id}`", inline=True)
    embed.add_field(name="<a:arrowyellow:1530241815121232072> Type", value=type_display, inline=True)
    embed.add_field(name="<a:crownyellow:1530251567880736788> Exchanger", value=exchanger.mention, inline=True)
    embed.add_field(name="<a:money:1530269856308531380> You Send", value=send_display, inline=True)
    embed.add_field(name="<a:money:1530269856308531380> You Receive", value=receive_display, inline=True)
    if ctx.guild.icon:
        embed.set_thumbnail(url=ctx.guild.icon.url)
    embed.set_footer(text=f"King Exchange & MM • Exchange • {datetime.now(IST).strftime('Today at %I:%M %p')}")

    await history_channel.send(embed=embed)
    await ctx.send("✅ Corrected exchange history sent.")
@bot.command(name="mmvouch")
@check_staff()
async def mmvouch(ctx, client: str = None, amount: str = None, mm_type: str = None):
    if client:
        try:
            client = await commands.MemberConverter().convert(ctx, client)
        except Exception:
            try:
                client_id = int(''.join(filter(str.isdigit, client)))
                client = ctx.guild.get_member(client_id)
            except Exception:
                return await ctx.send("❌ Could not find that user. Please mention them properly with @.")
    if not all([client, amount, mm_type]):
        return await ctx.send(
            "❌ Usage: `+mmvouch @client <amount> <inr/crypto>`\n"
            "Examples: `+mmvouch @john 5000 inr` | `+mmvouch @john 100 crypto`")
    mm_type = mm_type.lower()
    if mm_type not in ["inr", "crypto"]:
        return await ctx.send("❌ Invalid type. Use `inr` or `crypto`")

    amt_clean   = clean_float(amount)
    amt_display = f"₹{amt_clean:,.2f}" if mm_type == "inr" else f"${amt_clean:,.2f}"

    vouch_channel = ctx.guild.get_channel(VOUCH_CHANNEL_ID)
    vouch_mention = vouch_channel.mention if vouch_channel else "#vouch"
    rep_line      = f"+rep <@{ctx.author.id}> **MM HOLD [{amt_display}] SAFELY**"

    embed = discord.Embed(color=0x2b2d31)
    embed.description = (
        f"🔒 **DEAL SECURED!** 🔒\n\n"
        f"<@{ctx.author.id}> HAS SAFELY HOLD **{amt_display}** FOR THIS DEAL.\n"
        f"THANK YOU FOR TRUSTING OUR MIDDLEMAN SERVICE!\n\n"
        f"COPY THE LINE BELOW AND PASTE IT IN {vouch_mention} TO VOUCH 🏷️\n\n"
        f"```{rep_line}```"
    )
    await ctx.send(embed=embed)
    await ctx.send(rep_line)
    await ctx.send(f"{client.mention}, PLEASE VOUCH IN {vouch_mention} OR YOU MAY BE BLACKLISTED 🚫")

    await update_stats(ctx.author.id, amt_clean, "mm")

    cid_check = str(ctx.channel.id)
    ticket_check = await get_doc(tickets_col, cid_check)
    if ticket_check and ticket_check.get("client"):
        client_uid = str(ticket_check["client"])
        client_doc = await get_doc(client_stats_col, client_uid)
        if client_doc is None:
            client_doc = {"deals": 0, "volume": 0.0}
        client_doc["deals"] = int(client_doc.get("deals", 0)) + 1
        client_doc["volume"] = round(float(client_doc.get("volume", 0.0)) + float(amt_clean), 4)
        await set_doc(client_stats_col, client_uid, client_doc)

    cid    = str(ctx.channel.id)
    ticket = await get_doc(tickets_col, cid)
    if ticket:
        client_member = ctx.guild.get_member(ticket["client"])
        client_name   = client_member.name if client_member else "unknown"
        vouch_cat = None
        if str(VOUCH_PENDING_CATEGORY).isdigit():
            vouch_cat = ctx.guild.get_channel(int(VOUCH_PENDING_CATEGORY))
        if not vouch_cat:
            vouch_cat = discord.utils.get(ctx.guild.categories, name=str(VOUCH_PENDING_CATEGORY))
        if not vouch_cat:
            vouch_cat = await ctx.guild.create_category(str(VOUCH_PENDING_CATEGORY))
        ticket["vouch_pending"] = True
        ticket["exchanger"]     = ticket.get("exchanger") or ctx.author.id
        await set_doc(tickets_col, cid, ticket)
        try:
            await ctx.channel.edit(category=vouch_cat)
        except Exception:
            pass
        try:
            await ctx.channel.edit(name=f"💐┃vouch-{client_name}")
        except discord.HTTPException:
            pass
# ═══════════════════════════════════════════════════════════════════════════════
#  COMMANDS — STATS & LEADERBOARD
# ═══════════════════════════════════════════════════════════════════════════════

@bot.command(name="stats")
@check_staff()
async def stats(ctx, user: discord.Member = None):
    user   = user or ctx.author
    member = ctx.guild.get_member(user.id)
    joined = member.joined_at.strftime("%a %b %d %Y") if member and member.joined_at else "Unknown"

    stats_doc   = await get_doc(stats_col, str(user.id)) or {"trades": []}
    history     = stats_doc["trades"]
    exc_deals   = len(history)
    exc_vol     = sum(t["amount"] for t in history)
    exc_avg     = round(exc_vol / exc_deals, 2) if exc_deals > 0 else 0.0

    client_doc  = await get_doc(client_stats_col, str(user.id)) or {"deals": 0, "volume": 0.0}
    cli_deals   = client_doc["deals"]
    cli_vol     = round(client_doc["volume"], 2)
    cli_avg     = round(cli_vol / cli_deals, 2) if cli_deals > 0 else 0.0

    embed = discord.Embed(color=0xE67E22)
    embed.set_author(name="King Exchange & MM",
                     icon_url=ctx.guild.icon.url if ctx.guild.icon else bot.user.display_avatar.url)
    embed.title = f"{user.display_name}'s Statistics"
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.add_field(name="User Details:",
        value=f"ID : `{user.id}`\nMention : {user.mention}\nServer Joined : `{joined}`", inline=False)
    embed.add_field(name="Client Stats:",
        value=f"Total Deals : `{cli_deals}`\nTotal Exchanged : `${cli_vol}`\nAverage : `${cli_avg}`", inline=True)
    embed.add_field(name="Exchanger Stats:",
        value=f"Total Deals : `{exc_deals}`\nTotal Exchanged : `${exc_vol:.2f}`\nAverage : `${exc_avg}`", inline=True)
    await ctx.send(embed=embed)


@bot.command(name="p")
@check_staff()
async def profile(ctx, user: discord.Member = None):
    user    = user or ctx.author
    member  = ctx.guild.get_member(user.id)
    joined  = member.joined_at.strftime("%B %d, %Y") if member and member.joined_at else "Unknown"

    stats_doc   = await get_doc(stats_col, str(user.id)) or {"trades": []}
    total_deals = len(stats_doc["trades"])
    total_vol   = sum(t["amount"] for t in stats_doc["trades"])

    # ── TAX DISABLED ──────────────────────────────────────────────────────────
    # tax_doc   = await get_doc(tax_col, str(user.id)) or {"total_tax": 0.0, "paid_tax": 0.0}
    # total_tax = round(tax_doc["total_tax"], 4)
    # paid_tax  = round(tax_doc["paid_tax"],  4)
    # remaining = round(total_tax - paid_tax, 4)
    # ─────────────────────────────────────────────────────────────────────────

    limit_doc = await get_doc(limits_col, str(user.id))
    limit     = limit_doc["limit"] if limit_doc else None
    is_staff_member = is_staff(type("obj", (), {"author": user, "guild": ctx.guild})())

    embed = discord.Embed(title="🪙 EXCHANGER PROFILE", color=0x2b2d31)
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.add_field(name="Display Name",          value=f"`{user.display_name}`",   inline=True)
    embed.add_field(name="Server Joined",         value=f"`{joined}`",              inline=True)
    if not is_staff_member:
        limit_display = "N/A"
    elif limit is None:
        limit_display = "Unlimited"
    else:
        limit_display = f"${limit}"
    embed.add_field(name="Exchange Limit",        value=f"`{limit_display}`",              inline=True)
    embed.add_field(name="Total Deals",           value=f"`{total_deals}`",         inline=True)
    embed.add_field(name="Total Volume",          value=f"`{total_vol:.3f} USD`",   inline=True)
    # embed.add_field(name="Tax Due",               value=f"`${remaining}`",          inline=True)  # TAX DISABLED
    embed.set_footer(text=f"King Exchange • {datetime.now().strftime('Today at %I:%M %p')}")
    await ctx.send(embed=embed)

@bot.command(name="ds", aliases=["summary"])
@check_staff()
async def deal_summary(ctx):
    if not is_owner(ctx): return await ctx.send("❌ Owner only.")
    now         = datetime.now(IST)
    day_start   = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start  = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    all_stats = await get_all(stats_col)
    daily_vol = weekly_vol = monthly_vol = lifetime_vol = 0.0

    # Extract manual overrides — these REPLACE real totals if set
    manual_doc = all_stats.pop("ds_manual", None)
    manual_daily = manual_weekly = manual_monthly = manual_lifetime = None
    if manual_doc:
        for t in manual_doc.get("trades", []):
            label = t.get("label", "")
            amt   = t.get("amount", 0.0)
            if label == "daily":    manual_daily    = amt
            if label == "weekly":   manual_weekly   = amt
            if label == "monthly":  manual_monthly  = amt
            if label == "lifetime": manual_lifetime = amt

    # Sum real trades
    for uid, data in all_stats.items():
        for t in data.get("trades", []):
            try:
                t_time = datetime.fromisoformat(t["time"]).replace(tzinfo=None)
                now_naive = now.replace(tzinfo=None)
                day_start_naive   = day_start.replace(tzinfo=None)
                week_start_naive  = week_start.replace(tzinfo=None)
                month_start_naive = month_start.replace(tzinfo=None)
                amt    = t["amount"]
                lifetime_vol += amt
                if t_time >= month_start_naive: monthly_vol += amt
                if t_time >= week_start_naive:  weekly_vol  += amt
                if t_time >= day_start_naive:   daily_vol   += amt
            except Exception:
                pass

    # Manual overrides REPLACE real totals (None means not set)
    if manual_daily    is not None: daily_vol    = manual_daily
    if manual_weekly   is not None: weekly_vol   = manual_weekly
    if manual_monthly  is not None: monthly_vol  = manual_monthly
    if manual_lifetime is not None: lifetime_vol = manual_lifetime

    embed = discord.Embed(title="🤑 Exchange Deal Summary", color=0x5865f2)
    embed.add_field(name="• Daily:",    value=f"`{daily_vol:.2f}$`",    inline=False)
    embed.add_field(name="• Weekly:",   value=f"`{weekly_vol:.2f}$`",   inline=False)
    embed.add_field(name="• Monthly:",  value=f"`{monthly_vol:.2f}$`",  inline=False)
    embed.add_field(name="• Lifetime:", value=f"`{lifetime_vol:.2f}$`", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="lb", aliases=["leaderboard"])
@check_staff()
async def leaderboard(ctx, size: str = "10"):
    size     = int(clean_float(size)) if clean_float(size) in [10, 20, 50] else 10
    all_s    = await get_all(stats_col)
    sorted_s = sorted(all_s.items(),
                      key=lambda x: sum(t["amount"] for t in x[1].get("trades", [])),
                      reverse=True)[:size]

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    desc   = ""
    for i, (uid, data) in enumerate(sorted_s, 1):
        vol   = sum(t["amount"] for t in data.get("trades", []))
        medal = medals.get(i, f"**#{i}**")
        desc += f"{medal} <@{uid}> — `${vol:,.3f}`\n"

    embed = discord.Embed(title="🏆 King Exchanger Leaderboard", color=0x5865f2,
                          description=desc or "No data yet.")
    embed.set_footer(text=f"Showing Top {size}")
    await ctx.send(embed=embed)

# ═══════════════════════════════════════════════════════════════════════════════
#  COMMANDS — TAX  (DISABLED)
# ═══════════════════════════════════════════════════════════════════════════════

# @bot.command(name="addtax")
# async def addtax(ctx, user: discord.Member = None, *, amount: str = None):
#     if not is_owner(ctx): return await ctx.send("❌ Owner only.")
#     if not user or not amount: return await ctx.send("❌ Usage: `+addtax @user <amount>`")
#     amt = clean_float(amount)
#     if amt <= 0: return await ctx.send("❌ Amount must be greater than 0.")
#     await update_tax(user.id, amt)
#     tax_doc   = await get_doc(tax_col, str(user.id))
#     remaining = round(tax_doc["total_tax"] - tax_doc["paid_tax"], 4)
#     await ctx.send(f"✅ Added `${amt}` tax to {user.mention} | Due: `${remaining}`")


# @bot.command(name="paidtax")
# async def paidtax(ctx, user: discord.Member = None, *, amount: str = None):
#     if not is_owner(ctx): return await ctx.send("❌ Owner only.")
#     if not user or not amount: return await ctx.send("❌ Usage: `+paidtax @user <amount>`")
#     amt     = clean_float(amount)
#     uid     = str(user.id)
#     tax_doc = await get_doc(tax_col, uid)
#     if not tax_doc: return await ctx.send(f"❌ {user.mention} has no tax record.")
#     tax_doc["paid_tax"] = round(tax_doc["paid_tax"] + amt, 4)
#     tax_doc["history"].append({"time": datetime.now().isoformat(), "amount": amt, "type": "paid"})
#     await set_doc(tax_col, uid, tax_doc)
#     remaining = round(tax_doc["total_tax"] - tax_doc["paid_tax"], 4)
#     await ctx.send(f"✅ `${amt}` paid for {user.mention} | Due: `${remaining}`")

# @bot.command(name="taxlist")
# async def taxlist(ctx):
#     if not is_owner(ctx): return await ctx.send("❌ Owner only.")
#     all_tax = await get_all(tax_col)
#     if not all_tax: return await ctx.send("No tax records found.")
#     embed   = discord.Embed(title="💰 Tax Summary", color=0x5865f2)
#     for uid, data in all_tax.items():
#         remaining = round(data["total_tax"] - data["paid_tax"], 4)
#         if remaining > 0:
#             embed.add_field(name=f"<@{uid}>",
#                 value=f"Due: `${remaining}` | Total: `${data['total_tax']}` | Paid: `${data['paid_tax']}`",
#                 inline=False)
#     if not embed.fields: embed.description = "✅ All taxes are paid!"
#     await ctx.send(embed=embed)

@bot.command(name="addtrade")
async def addtrade(ctx, user: discord.Member = None, amount: str = None, trade_type: str = "manual"):
    if not is_owner(ctx): return await ctx.send("❌ Owner only.")
    if not user or not amount: return await ctx.send("❌ Usage: `.addtrade @user <amount> [i2c/c2i/c2c]`")
    amt = clean_float(amount)
    if amt <= 0: return await ctx.send("❌ Amount must be greater than 0.")
    trade_type = trade_type.lower() if trade_type.lower() in ["i2c", "c2i", "c2c"] else "manual"
    await update_stats(user.id, amt, trade_type)
    await ctx.send(f"✅ Added trade of `${amt}` ({trade_type}) for {user.mention}")

@bot.command(name="removetrade")
async def removetrade(ctx, user: discord.Member = None, amount: str = None):
    if not is_owner(ctx): return await ctx.send("❌ Owner only.")
    if not user or not amount: return await ctx.send("❌ Usage: `.removetrade @user <amount>`")
    amt     = clean_float(amount)
    uid     = str(user.id)
    doc     = await get_doc(stats_col, uid) or {"trades": []}
    trades  = doc["trades"]
    # Remove the trade closest to the given amount
    for i, t in enumerate(trades):
        if abs(t["amount"] - amt) < 0.01:
            trades.pop(i)
            doc["trades"] = trades
            await set_doc(stats_col, uid, doc)
            return await ctx.send(f"✅ Removed trade of `${amt}` from {user.mention}")
    await ctx.send(f"❌ No trade found with amount `${amt}` for {user.mention}")

@bot.command(name="setvolume")
async def setvolume(ctx, user: discord.Member = None, *, amount: str = None):
    if not is_owner(ctx): return await ctx.send("❌ Owner only.")
    if not user or not amount: return await ctx.send("❌ Usage: `.setvolume @user <amount>`")
    amt  = clean_float(amount)
    uid  = str(user.id)
    doc  = await get_doc(stats_col, uid) or {"trades": []}
    current_vol = sum(t["amount"] for t in doc["trades"])
    if current_vol > 0:
        # Scale all trades proportionally
        ratio = amt / current_vol
        for t in doc["trades"]:
            t["amount"] = round(t["amount"] * ratio, 4)
    else:
        doc["trades"] = [{"time": datetime.now().isoformat(), "amount": amt, "type": "manual"}]
    await set_doc(stats_col, uid, doc)
    await ctx.send(f"✅ Volume for {user.mention} set to `${amt}`")

@bot.command(name="setds")
async def setds(ctx, period: str = None, *, amount: str = None):
    if not is_owner(ctx): return await ctx.send("❌ Owner only.")
    if not period or not amount:
        return await ctx.send(
            "❌ Usage: `.setds <period> <amount>`\n"
            "Periods: `daily`, `weekly`, `monthly`, `lifetime`\n"
            "Example: `.setds daily 500`"
        )
    period = period.lower()
    if period not in ["daily", "weekly", "monthly", "lifetime"]:
        return await ctx.send("❌ Period must be `daily`, `weekly`, `monthly` or `lifetime`")

    raw = amount.strip()
    negative = raw.startswith("-")
    amt = clean_float(raw)
    if negative:
        amt = -amt
    now = datetime.now(IST)

    # Determine the time to stamp the manual trade
    if period == "daily":
        trade_time = now.replace(hour=1, minute=0, second=0, microsecond=0)
    elif period == "weekly":
        trade_time = (now - timedelta(days=now.weekday())).replace(hour=1, minute=0, second=0, microsecond=0)
    elif period == "monthly":
        trade_time = now.replace(day=1, hour=1, minute=0, second=0, microsecond=0)
    else:  # lifetime
        trade_time = datetime(2020, 1, 1, 0, 0, 0)

    # Save under a special "ds_manual" user key
    uid = "ds_manual"
    doc = await get_doc(stats_col, uid) or {"trades": []}

    # Remove existing manual trade for this period
    period_markers = {
        "daily":    lambda t: datetime.fromisoformat(t["time"]).date() == now.date(),
        "weekly":   lambda t: datetime.fromisoformat(t["time"]) >= (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0) and t.get("label") == "weekly",
        "monthly":  lambda t: datetime.fromisoformat(t["time"]).month == now.month and datetime.fromisoformat(t["time"]).year == now.year and t.get("label") == "monthly",
        "lifetime": lambda t: t.get("label") == "lifetime",
    }

    doc["trades"] = [t for t in doc["trades"] if t.get("label") != period]
    doc["trades"].append({
        "time":   trade_time.isoformat(),
        "amount": amt,
        "type":   "manual",
        "label":  period
    })
    await set_doc(stats_col, uid, doc)
    sign = "-" if amt < 0 else ""
    await ctx.send(f"✅ `.ds` **{period}** manually set to `{sign}${abs(amt):.2f}` — this will now override real trades for this period.")

@bot.command(name="resetds")
async def resetds(ctx, period: str = None):
    if not is_owner(ctx): return await ctx.send("❌ Owner only.")
    if not period or period.lower() not in ["daily", "weekly", "monthly", "lifetime", "all"]:
        return await ctx.send("❌ Usage: `.resetds <daily/weekly/monthly/lifetime/all>`")
    period = period.lower()
    uid = "ds_manual"
    doc = await get_doc(stats_col, uid) or {"trades": []}
    if period == "all":
        doc["trades"] = []
    else:
        doc["trades"] = [t for t in doc["trades"] if t.get("label") != period]
    await set_doc(stats_col, uid, doc)
    await ctx.send(f"✅ `.ds` **{period}** override cleared — now showing real trades again.")
# ═══════════════════════════════════════════════════════════════════════════════
#  COMMANDS — TICKET TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

@bot.command()
@check_staff()
async def dn(ctx):
    cid    = str(ctx.channel.id)
    ticket = await get_doc(tickets_col, cid)
    if not ticket: return await ctx.send("❌ Not a ticket channel.")

    if ticket.get("is_support"):
        return await ctx.send("❌ Support tickets can't be closed with `+dn`. Use `+sclose` instead.")

    await ctx.send("⌛ Archiving trade and generating transcript...")
    transcript = await chat_exporter.export(ctx.channel, tz_info="Asia/Kolkata", military_time=True)

    if transcript:
        # Build transcript embed FIRST
        type_display_map = {
            "i2c": "I2C", "c2i": "C2I", "c2c": "C2C",
            "cash_i2c": "Cash Exchange (I2C)",
            "cash_c2i": "Cash Exchange (C2I)",
            "support_help": "Support (Help Ticket)",
            "support_report": "Support (Report Exchanger)",
        }
        client_user    = None
        exchanger_user = None
        try:
            if ticket["client"]:
                client_user = await bot.fetch_user(ticket["client"])
            if ticket["exchanger"]:
                exchanger_user = await bot.fetch_user(ticket["exchanger"])
        except Exception:
            pass

        transcript_embed = discord.Embed(title="King Ticket System - Transcript", color=0x2b2d31)
        transcript_embed.description = f"Transcript for **{ctx.channel.name}** has been generated successfully."
        transcript_embed.add_field(name="Category", value=type_display_map.get(ticket["type"], "N/A"), inline=True)
        transcript_embed.add_field(name="Client",   value=client_user.mention if client_user else "Unknown", inline=True)
        transcript_embed.add_field(name="Exchanger",value=exchanger_user.mention if exchanger_user else "Unknown", inline=True)
        if ticket.get("is_support"):
            amt_display = "N/A (Support Ticket)"
        elif ticket["type"] in ("i2c", "cash_i2c"):
            raw_amt   = clean_float(ticket["amount"])
            rates_doc = await get_doc(rates_col, "rates") or {}
            i2c_rate  = clean_float(rates_doc.get("i2c_rate", "99"))
            usd_amt   = round(raw_amt / i2c_rate, 4) if i2c_rate > 0 else raw_amt
            amt_display = f"₹{raw_amt} (≈ ${usd_amt})"
        else:
            raw_amt   = clean_float(ticket["amount"])
            amt_display = f"${raw_amt}"
        transcript_embed.add_field(name="Amount", value=amt_display, inline=False)
        transcript_embed.set_footer(text=f"King Exchange & MM • Today at {datetime.now(IST).strftime('%I:%M %p')}")

        archive_map = {
            "i2c": I2C_ARCHIVES_ID,
            "c2i": C2I_ARCHIVES_ID,
            "c2c": C2C_ARCHIVES_ID,
            "cash_i2c": CASH_EXCHANGE_ARCHIVES_ID,
            "cash_c2i": CASH_EXCHANGE_ARCHIVES_ID,
            "support_help": SUPPORT_ARCHIVES_ID,
            "support_report": SUPPORT_ARCHIVES_ID,
        }
        arch        = ctx.guild.get_channel(archive_map.get(ticket["type"], 0))
        if arch:
            for attempt in range(3):
                try:
                    await arch.send(
                        embed=transcript_embed,
                        file=discord.File(io.BytesIO(transcript.encode()), filename=f"{ctx.channel.name}.html")
                    )
                    break
                except Exception as e:
                    if attempt == 2: await ctx.send(f"⚠️ Archive failed: {e}")
                    else: await asyncio.sleep(2)

        for uid in [ticket["client"], ticket["exchanger"]]:
            if uid:
                try:
                    u = await bot.fetch_user(uid)
                    await u.send(
                        embed=transcript_embed,
                        file=discord.File(io.BytesIO(transcript.encode()), filename=f"{ctx.channel.name}.html")
                    )
                except Exception: pass

    ticket["review_pending"] = True
    ticket["vouch_pending"]  = False
    await set_doc(tickets_col, cid, ticket)

    done_cat = ctx.guild.get_channel(DONE_CATEGORY_ID)
    if done_cat:
        try:
            await ctx.channel.edit(category=done_cat)
        except Exception:
            pass
    try:
        await ctx.channel.edit(name=f"✅┃done-{ticket['ticket_number']}")
    except discord.HTTPException:
        pass

    await ctx.send(
        "✅ Transcript archived and sent. This ticket has been moved to review.\n"
        "🔒 A moderator will close it with `+approve` after reviewing."
    )

@bot.command(name="approve")
@check_staff()
async def approve(ctx):
    cid    = str(ctx.channel.id)
    ticket = await get_doc(tickets_col, cid)
    if not ticket:
        return await ctx.send("❌ Not a ticket channel.")
    if not ticket.get("review_pending"):
        return await ctx.send("❌ This ticket hasn't been sent for review yet. Run `+dn` first.")

    await ctx.send("🗑️ Approved. Closing in 3 seconds...")
    await tickets_col.delete_one({"_id": cid})
    await asyncio.sleep(3)
    await ctx.channel.delete()

@bot.command(name="sclose")
@check_staff()
async def sclose(ctx):
    cid    = str(ctx.channel.id)
    ticket = await get_doc(tickets_col, cid)
    if not ticket: return await ctx.send("❌ Not a ticket channel.")
    if not ticket.get("is_support"):
        return await ctx.send("❌ This isn't a support ticket. Use `+dn` instead.")

    await ctx.send("⌛ Archiving ticket and generating transcript...")
    transcript = await chat_exporter.export(ctx.channel, tz_info="Asia/Kolkata", military_time=True)

    if transcript:
        type_display_map = {
            "support_help": "Support (Help Ticket)",
            "support_report": "Support (Report Exchanger)",
        }
        client_user = None
        try:
            if ticket["client"]:
                client_user = await bot.fetch_user(ticket["client"])
        except Exception:
            pass

        transcript_embed = discord.Embed(title="King Ticket System - Transcript", color=0x2b2d31)
        transcript_embed.description = f"Transcript for **{ctx.channel.name}** has been generated successfully."
        transcript_embed.add_field(name="Category", value=type_display_map.get(ticket["type"], "N/A"), inline=True)
        transcript_embed.add_field(name="Client",   value=client_user.mention if client_user else "Unknown", inline=True)
        transcript_embed.add_field(name="Closed By", value=ctx.author.mention, inline=True)
        transcript_embed.set_footer(text=f"King Exchange & MM • Today at {datetime.now(IST).strftime('%I:%M %p')}")

        arch = ctx.guild.get_channel(SUPPORT_ARCHIVES_ID)
        if arch:
            for attempt in range(3):
                try:
                    await arch.send(
                        embed=transcript_embed,
                        file=discord.File(io.BytesIO(transcript.encode()), filename=f"{ctx.channel.name}.html")
                    )
                    break
                except Exception as e:
                    if attempt == 2: await ctx.send(f"⚠️ Archive failed: {e}")
                    else: await asyncio.sleep(2)

        # DM only the client
        if ticket.get("client"):
            try:
                u = await bot.fetch_user(ticket["client"])
                await u.send(
                    embed=transcript_embed,
                    file=discord.File(io.BytesIO(transcript.encode()), filename=f"{ctx.channel.name}.html")
                )
            except Exception:
                pass

    await tickets_col.delete_one({"_id": cid})
    await asyncio.sleep(2)
    await ctx.channel.delete()

@bot.command(name="transcript")
@check_staff()
async def transcript_cmd(ctx):
    await ctx.send("⌛ Generating transcript...")
    transcript = await chat_exporter.export(ctx.channel, tz_info="Asia/Kolkata", military_time=True)
    if not transcript: return await ctx.send("❌ Failed to generate transcript.")
    try:
        await ctx.author.send(
            f"📄 Transcript for `{ctx.channel.name}`:",
            file=discord.File(io.BytesIO(transcript.encode()), filename=f"{ctx.channel.name}.html")
        )
        await ctx.send("✅ Transcript sent to your DMs.")
    except Exception:
        await ctx.send("❌ Could not DM you. Enable DMs from server members.")


@bot.command(name="unclaim", aliases=["uc"])
@check_staff()
async def unclaim(ctx):
    cid    = str(ctx.channel.id)
    ticket = await get_doc(tickets_col, cid)
    if not ticket: return await ctx.send("❌ Not a ticket channel.")
    if not ticket["exchanger"]: return await ctx.send("❌ Ticket is not claimed yet.")
    if ticket["exchanger"] != ctx.author.id and not is_owner(ctx):
        return await ctx.send("❌ Only the exchanger who claimed this ticket can unclaim it.")

    old_exchanger       = ticket["exchanger"]
    ticket["exchanger"] = None
    await set_doc(tickets_col, cid, ticket)

    # Rename back to original ticket name
    type_names = {
        "i2c":      f"🎫┃i2c-{ticket['ticket_number']}",
        "c2i":      f"💵┃c2i-{ticket['ticket_number']}",
        "c2c":      f"🏦┃c2c-{ticket['ticket_number']}",
        "mm":       f"🎟┃mm-{ticket['ticket_number']}",
        "cash_i2c": f"🛡️┃cash-i2c-{ticket['ticket_number']}",
        "cash_c2i": f"🛡️┃cash-c2i-{ticket['ticket_number']}",
        "support_help":   f"📩┃support-{ticket['ticket_number']}",
        "support_report": f"🚨┃report-{ticket['ticket_number']}",
    }
    new_name = type_names.get(ticket["type"], ctx.channel.name)
    try:
        await ctx.channel.edit(name=new_name)
    except discord.HTTPException:
        pass  # Skip if rate limited

    embed = discord.Embed(title="Ticket Unclaimed", color=0xED4245,
        description=f"<@{old_exchanger}> has unclaimed this ticket.\nAnother exchanger can now claim it.")
    await ctx.send(embed=embed, view=ClaimView())

@bot.command(name="adduser")
@check_staff()
@commands.has_permissions(manage_channels=True)
async def adduser(ctx, user: discord.Member = None):
    if not user: return await ctx.send("❌ Usage: `.adduser @user`")
    cid = str(ctx.channel.id)
    if not await get_doc(tickets_col, cid): return await ctx.send("❌ Not a ticket channel.")
    await ctx.channel.set_permissions(user, view_channel=True, send_messages=True)
    await ctx.send(f"✅ {user.mention} added to ticket.")


@bot.command(name="removeuser")
@check_staff()
@commands.has_permissions(manage_channels=True)
async def removeuser(ctx, user: discord.Member = None):
    if not user: return await ctx.send("❌ Usage: `.removeuser @user`")
    cid = str(ctx.channel.id)
    if not await get_doc(tickets_col, cid): return await ctx.send("❌ Not a ticket channel.")
    await ctx.channel.set_permissions(user, overwrite=None)
    await ctx.send(f"✅ {user.mention} removed from ticket.")


@bot.command(name="close")
async def close(ctx):
    if not is_owner(ctx): return await ctx.send("❌ Owner only.")
    cid = str(ctx.channel.id)
    if not await get_doc(tickets_col, cid): return await ctx.send("❌ Not a ticket channel.")
    embed = discord.Embed(title="⚠️ Close Ticket?",
        description="Click to confirm closing this ticket without transcript.", color=0xED4245)
    await ctx.send(embed=embed, view=ConfirmCloseView(ctx.author.id))

@bot.command(name="ss")
@check_staff()
async def screenshot(ctx):
    cid    = str(ctx.channel.id)
    ticket = await get_doc(tickets_col, cid)

    if not ticket:
       return await ctx.send("❌ Not a ticket channel.")
    if ticket["type"] in ("support_help", "support_report"):
        return await ctx.send("❌ Support tickets cannot be unclaimed.")
    if ticket.get("exchanger") != ctx.author.id and not is_owner(ctx):
        return await ctx.send("❌ Only the claiming exchanger can use this.")

    client_member = ctx.guild.get_member(ticket["client"])

    embed = discord.Embed(title="Screenshot Proof Required", color=0xED4245)
    embed.description = (
        "📷 Please provide a screenshot following the instructions below:\n\n"
        "• Show the current Discord ticket screen\n"
        "• Show the INR payment screen\n"
        "• Minimize both apps\n"
        "• Take one screenshot showing both minimized apps"
    )
    embed.set_image(url="https://i.postimg.cc/nc1Y8nc4/splitss.jpg")
    embed.set_footer(text=f"King Exchange & MM • Proof Verification System • Today at {datetime.now().strftime('%I:%M %p')}")
    await ctx.message.delete()
    content = client_member.mention if client_member else ""
    await ctx.send(content=content, embed=embed)

# ═══════════════════════════════════════════════════════════════════════════════
#  SLASH COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

@bot.tree.command(name="setup_panel", description="Deploy the exchange panel")
@owner_only_slash()
async def setup_panel(interaction: discord.Interaction):
    rates = await get_doc(rates_col, "rates") or {}
    i2c   = rates.get("i2c_rate", "92").replace("/$", "")
    c2i_low  = rates.get("c2i_rate", "95").replace("/$", "")
    c2i_high = rates.get("c2i_high_rate", c2i_low).replace("/$", "")
    c2c   = rates.get("c2c_rate", "4").replace("%", "")

    embed = discord.Embed(title="KING EXCHANGE & MM", color=0x2b2d31)
    embed.description = (
        "<a:crownyellow:1530251567880736788> Exchange Rates <a:crownyellow:1530251567880736788>\n\n"
        f"<a:dollar:1530251618266906906> **INR TO CRYPTO**\n **<a:arrowyellow:1530241815121232072>** {i2c}/$ Any Amount\n\n"
        f"<a:dollar:1530251618266906906> **CRYPTO TO INR**\n **<a:arrowyellow:1530241815121232072>** Below 100$ : {c2i_low}/$\n **<a:arrowyellow:1530241815121232072>** Above 100$ : {c2i_high}/$\n\n"
        f"<a:dollar:1530251618266906906> **CRYPTO TO CRYPTO**\n **<a:arrowyellow:1530241815121232072>** {c2c}% Fees + Transaction Fees\n\n"
        "<a:check:1530250663206977701> Fixed Rates. No Negotiation.\n<a:check:1530250663206977701> Minimum exchange is 1$\n"
        "<a:check:1530250663206977701> Be patient. Don't ping.\n<a:check:1530250663206977701> Don't create tickets for fun."
    )
    if interaction.guild.icon: embed.set_thumbnail(url=interaction.guild.icon.url)
    else: embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text="King Exchange & MM • Fast Secure & Trusted")
    await interaction.channel.send(embed=embed, view=PanelView())
    await interaction.response.send_message("✅ Panel deployed.", ephemeral=True)
@bot.tree.command(name="setup_mm_panel", description="Deploy the middleman panel")
@owner_only_slash()
async def setup_mm_panel(interaction: discord.Interaction):
    rates = await get_doc(rates_col, "rates") or {}
    inr_low   = rates.get("mm_inr_low_fee", "5")
    inr_high  = rates.get("mm_inr_high_fee", "1")
    crypto_low  = rates.get("mm_crypto_low_fee", "0.1")
    crypto_high = rates.get("mm_crypto_high_fee", "1")

    embed = discord.Embed(title="KING EXCHANGE & MM", color=0x2b2d31)
    embed.description = (
        "<a:ticket:1530269895517016275> **Middleman Panel**\n\n"
        f"<a:arrowyellow:1530241815121232072> **INR MM**\n"
        f"<a:griffondot:1530242376264585247> Below ₹1000: ₹{inr_low} Fee\n\n"
        f"<a:griffondot:1530242376264585247> Above ₹1000: {inr_high}% Fee\n\n"
        f"<a:arrowyellow:1530241815121232072> **CRYPTO MM**\n"
        f"<a:griffondot:1530242376264585247> Below $100: ${crypto_low} Fee\n\n"
        f"<a:griffondot:1530242376264585247> Above $100: {crypto_high}% Fee\n\n"
        f"<a:arrowyellow:1530241815121232072> **Rules**\n"
        f"<a:arrowyellow:1530241815121232072> Fixed Rates - No Negotiations\n\n"
        f"<a:arrowyellow:1530241815121232072> Follow staff instructions carefully\n\n"
        f"<a:arrowyellow:1530241815121232072> Stay patient & avoid unnecessary pings"
    )
    if interaction.guild.icon: embed.set_thumbnail(url=interaction.guild.icon.url)
    else: embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text="King Exchange & MM • Middleman Service")
    await interaction.channel.send(embed=embed, view=MMPanelView())
    await interaction.response.send_message("✅ Middleman panel deployed.", ephemeral=True)


@bot.command(name="setupmm")
@check_owner()
async def setupmm_cmd(ctx):
    rates = await get_doc(rates_col, "rates") or {}
    inr_low   = rates.get("mm_inr_low_fee", "5")
    inr_high  = rates.get("mm_inr_high_fee", "1")
    crypto_low  = rates.get("mm_crypto_low_fee", "0.1")
    crypto_high = rates.get("mm_crypto_high_fee", "1")

    embed = discord.Embed(title="KING EXCHANGE & MM", color=0x2b2d31)
    embed.description = (
        "<a:ticket:1530269895517016275> **Middleman Panel**\n\n"
        f"<a:arrowyellow:1530241815121232072> **INR MM**\n"
        f"<a:griffondot:1530242376264585247> Below ₹1000: ₹{inr_low} Fee\n\n"
        f"<a:griffondot:1530242376264585247> Above ₹1000: {inr_high}% Fee\n\n"
        f"<a:arrowyellow:1530241815121232072> **CRYPTO MM**\n"
        f"<a:griffondot:1530242376264585247> Below $100: ${crypto_low} Fee\n\n"
        f"<a:griffondot:1530242376264585247> Above $100: {crypto_high}% Fee\n\n"
        f"<a:arrowyellow:1530241815121232072> **Rules**\n"
        f"<a:arrowyellow:1530241815121232072> Fixed Rates - No Negotiations\n\n"
        f"<a:arrowyellow:1530241815121232072> Follow staff instructions carefully\n\n"
        f"<a:arrowyellow:1530241815121232072> Stay patient & avoid unnecessary pings"
    )
    if ctx.guild.icon: embed.set_thumbnail(url=ctx.guild.icon.url)
    else: embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text="King Exchange & MM • Middleman Service")
    await ctx.message.delete()
    await ctx.send(embed=embed, view=MMPanelView())

@bot.tree.command(name="setup_support_panel", description="Deploy the support panel")
@owner_only_slash()
async def setup_support_panel(interaction: discord.Interaction):
    guild = interaction.guild
    embed_title = "KING EXCHANGE & MM - Support Hub"
    embed = discord.Embed(title=embed_title, color=0x2b2d31)
    embed.description = (
        "<a:griffondot:1530242376264585247> **Need Assistance?** Open a ticket if you have questions, need guidance, or require support regarding exchanges.\n"
        "<a:griffondot:1530242376264585247> **Report an Issue?** If an exchanger scams or acts suspiciously, report them here immediately.\n\n"
        "<a:arrowyellow:1530241815121232072> **Select a category below to proceed:**\n\n"
        "<a:griffondot:1530242376264585247> **Support Ticket** – Get support for exchange-related queries, or any other type of support.\n"
        "<a:griffondot:1530242376264585247> **Report Exchanger** – Report fraudulent or suspicious exchangers.\n\n"
        "<a:alarm:1530248514095943720> **False reports may lead to consequences.**"
    )
    if guild and guild.icon: embed.set_thumbnail(url=guild.icon.url)
    else: embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text="King Exchange & MM • Support & Safety Hub")
    await interaction.channel.send(embed=embed, view=SupportPanelView())
    await interaction.response.send_message("✅ Support panel deployed.", ephemeral=True)


@bot.command(name="setupsupport", aliases=["setup_support_panel"])
@check_owner()
async def setupsupport_cmd(ctx):
    guild = ctx.guild
    embed_title = "King Exchange & MM - Support Hub"
    embed = discord.Embed(title=embed_title, color=0x2b2d31)
    embed.description = (
        "• **Need Assistance?** Open a ticket if you have questions, need guidance, or require support regarding exchanges.\n"
        "• **Report an Issue?** If an exchanger scams or acts suspiciously, report them here immediately.\n\n"
        "➡️ **Select a category below to proceed:**\n\n"
        "• **Support Ticket** – Get support for exchange-related queries, or any other type of support.\n"
        "• **Report Exchanger** – Report fraudulent or suspicious exchangers.\n\n"
        "🚨 **False reports may lead to consequences.**"
    )
    if guild and guild.icon: embed.set_thumbnail(url=guild.icon.url)
    else: embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text="King Exchange & MM • Support & Safety Hub")
    await ctx.message.delete()
    await ctx.send(embed=embed, view=SupportPanelView())


# ── Safe Exchange Panel ────────────────────────────────────────────────────────

@bot.tree.command(name="setup_cash_panel", description="Deploy the Cash Exchange panel (min $50)")
@owner_only_slash()
async def setup_cash_panel(interaction: discord.Interaction):
    rates    = await get_doc(rates_col, "rates") or {}
    i2c      = rates.get("i2c_rate", "92").replace("/$", "")
    c2i_low  = rates.get("c2i_rate", "95").replace("/$", "")
    c2i_high = rates.get("c2i_high_rate", c2i_low).replace("/$", "")

    embed = discord.Embed(title="<a:crownyellow:1530251567880736788> KING EXCHANGE • 🛡️ CASH EXCHANGE", color=0x2b2d31)
    embed.description = (
        "<a:crownyellow:1530251567880736788> Cash Exchange Rates <a:crownyellow:1530251567880736788>\n\n"
        f"<a:dollar:1530251618266906906> **INR TO CRYPTO**\n **<a:arrowyellow:1530241815121232072>** {i2c}/$ Any Amount\n\n"
        f"<a:dollar:1530251618266906906> **CRYPTO TO INR**\n **<a:arrowyellow:1530241815121232072>** Below 100$ : {c2i_low}/$\n **<a:arrowyellow:1530241815121232072>** Above 100$ : {c2i_high}/$\n\n"
        "<a:check:1530250663206977701> Fixed Rates. No Negotiation.\n"
        "<a:check:1530250663206977701> **Minimum $50 only.**\n"
        "<a:check:1530250663206977701> Be patient. Don't ping.\n"
        "<a:check:1530250663206977701> Don't create tickets for fun."
    )
    if interaction.guild.icon: embed.set_thumbnail(url=interaction.guild.icon.url)
    else: embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text="King Exchange & MM • Cash Exchange • Fast Secure & Trusted")
    await interaction.channel.send(embed=embed, view=CashExchangePanelView())
    await interaction.response.send_message("✅ Cash Exchange panel deployed.", ephemeral=True)

@bot.command(name="setupcash")
@check_owner()
async def setupcash_cmd(ctx):
    rates    = await get_doc(rates_col, "rates") or {}
    i2c      = rates.get("i2c_rate", "92").replace("/$", "")
    c2i_low  = rates.get("c2i_rate", "95").replace("/$", "")
    c2i_high = rates.get("c2i_high_rate", c2i_low).replace("/$", "")

    embed = discord.Embed(title="<a:crownyellow:1530251567880736788> KING EXCHANGE • 🛡️ CASH EXCHANGE", color=0x2b2d31)
    embed.description = (
        "<a:crownyellow:1530251567880736788> Cash Exchange Rates <a:crownyellow:1530251567880736788>\n\n"
        f"<a:dollar:1530251618266906906> **INR TO CRYPTO**\n **<a:arrowyellow:1530241815121232072>** {i2c}/$ Any Amount\n\n"
        f"<a:dollar:1530251618266906906> **CRYPTO TO INR**\n **<a:arrowyellow:1530241815121232072>** Below 100$ : {c2i_low}/$\n **<a:arrowyellow:1530241815121232072>** Above 100$ : {c2i_high}/$\n\n"
        "<a:check:1530250663206977701> Fixed Rates. No Negotiation.\n"
        "<a:check:1530250663206977701> **Minimum $50 only.**\n"
        "<a:check:1530250663206977701> Be patient. Don't ping.\n"
        "<a:check:1530250663206977701> Don't create tickets for fun."
    )
    if ctx.guild.icon: embed.set_thumbnail(url=ctx.guild.icon.url)
    else: embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text="King Exchange & MM • Cash Exchange • Fast Secure & Trusted")
    await ctx.message.delete()
    await ctx.send(embed=embed, view=CashExchangePanelView())

# ═══════════════════════════════════════════════════════════════════════════════
#  EVENTS
# ═══════════════════════════════════════════════════════════════════════════════

CRYPTO_KEYWORDS = ["usdt", "ltc", "btc", "sol", "eth", "trx", "bnb", "xrp", "cw", "cwallet", "usdc", "ton", "doge", "matic", "ada", "dot", "avax", "link", "uni", "atom"]

@bot.event
async def on_message(message):
    if message.author.bot: return
    await bot.process_commands(message)

    # ── Vouch detection ───────────────────────────────────────────────────────
    if message.channel.id == VOUCH_CHANNEL_ID and not message.author.bot:
        content_check = message.content.lower()
        if "+rep" in content_check and "exchanged" in content_check:
            await message.add_reaction("✅")

            # Find matching ticket in vouch pending and mark vouch done
            all_tickets = await get_all(tickets_col)
            for cid, ticket in all_tickets.items():
                if ticket.get("vouch_pending") and ticket.get("exchanger"):
                    exchanger_id = str(ticket["exchanger"])
                    if f"<@{exchanger_id}>" in message.content or exchanger_id in message.content:
                        ticket["vouch_done"] = True
                        await set_doc(tickets_col, cid, ticket)

                        pass
                        break

    content = message.content.lower().strip()
    if content.startswith("+"):
        parts = content[1:].split()
        cmd   = parts[0] if parts else ""

        # +upi1, +upi2 etc — fetch UPI by slot number
        if cmd.startswith("upi") and len(cmd) > 3 and cmd[3:].isdigit():
            if not is_staff(message):
                await message.channel.send("❌ Staff only.")
                return
            slot  = int(cmd[3:])
            doc   = await get_doc(wallets_col, str(message.author.id)) or {}
            items = doc.get("upis", [])
            if not items:
                await message.channel.send("❌ No UPIs saved.")
            elif slot < 1 or slot > len(items):
                await message.channel.send(f"❌ You have {len(items)} UPI(s).")
            else:
                item = items[slot - 1]
                await message.channel.send(f"UPI: `{item['value']}`")
            return

        # Search any label from addresses or IDs
        elif len(parts) == 1 and cmd not in [
    "help", "v", "vouch", "dn", "p", "lb", "stats", "daily", "weekly", "entire", "summary",
    "manage", "upi", "addy", "address", "id", "mmqr", "qr", "calc", "i2c", "c2i", "set",
    "setlimit", "addtax", "paidtax", "taxlist", "fixtickets", "setrate", "transcript",
    "claim", "c", "unclaim", "uc", "u", "adduser", "removeuser", "close", "approve", "sclose",
    "addupi", "addaddy", "addid", "delupi", "deladdy", "delid", "ss", "editstats",
    "addtrade", "removetrade", "setvolume", "ds", "setds", "resetds", "resetcounters",
    "setcounter", "setupmm", "setupsupport", "setupcash", "pn", "vanity", "mmvouch", "fixhistory"
]:
            doc      = await get_doc(wallets_col, str(message.author.id)) or {}
            addys    = [normalize_wallet_item(i) for i in doc.get("addys", [])]
            ids      = [normalize_wallet_item(i) for i in doc.get("ids", [])]

            matched_addy = [item for item in addys if item["label"].lower() == cmd]
            matched_id   = [item for item in ids   if item["label"].lower() == cmd]

            if (matched_addy or matched_id) and not is_staff(message):
                await message.channel.send("❌ Staff only.")
                return
            if matched_addy:
                await message.channel.send(f"**{matched_addy[0]['label']} Address:**\n```{matched_addy[0]['value']}```")
            elif matched_id:
                await message.channel.send(f"**{matched_id[0]['label']} ID:**\n```{matched_id[0]['value']}```")
            # Don't show all addresses if nothing matches — just silently ignore


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Administrators only.", delete_after=5)
    elif isinstance(error, commands.CheckFailure):
        await ctx.send(str(error), delete_after=5)
    elif isinstance(error, commands.CommandNotFound):
        pass
    elif isinstance(error, commands.MemberNotFound):
        pass
    elif isinstance(error, commands.BadArgument):
        pass
    else:
        raise error

@bot.event
async def on_connect():
    print("CONNECTED TO DISCORD", flush=True)

@bot.event
async def setup_hook():
    print("SETUP HOOK", flush=True)

@bot.event
async def on_ready():
    print("=== ON_READY STARTED ===", flush=True)

    try:
        bot.add_view(PanelView())
        bot.add_view(SupportPanelView())
        bot.add_view(MMPanelView())
        bot.add_view(ClaimView())
        bot.add_view(CashExchangePanelView())

        await bot.tree.sync()

        print(f"Logged in as {bot.user} ({bot.user.id})", flush=True)

        await mongo_client.admin.command("ping")
        print("MongoDB connected successfully", flush=True)

    except Exception as e:
        print("ON_READY ERROR:", e, flush=True)

print("Starting bot...", flush=True)
bot.run(BOT_TOKEN)
import discord
from discord.ext import commands, tasks
import datetime
import pytz
import json
import requests
import asyncio
import os
from myserver import server_on
# ================= TOKEN =================
# Token อยู่ใน railway
# ================= ID CHANNEL =================
OWNER_ID = 848068744303083551 # ID admin
# ================== CHANNEL ==================
LOG_CHANNEL_ID = 1470417750319960168 # ห้อง embed บอทซื้อยศอั่งเปา + ส่งข้อความลูปทุกๆ 1 ชั่วโมง
ANGPAO_CHANNEL_ID = 1470403835234357258 # ห้องคนส่งลิ้งก์อั่งเปามาให้ (ห้องรับตังค์)
SUCCESS_CHANNEL_ID = 1470997698004914197 # embed ซื้อยศสำเร็จ
# ================== ROLE ==================
ROLE_01 = 1082885961953853540 # บทบาท 1
ROLE_02 = 1082668970718527508 # บทบาท 2
ROLE_03 = 1082667309254054008 # บทบาท 3
ROLE_04 = 1082667313163157515 # บทบาท 4
# ================= INTENTS =================
intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

cooldown = {}
pending_links = {}
# ================= BASE EMBED =================
def create_base_embed(title, member):
    embed = discord.Embed(
        title=title,
        color=0x00ff00
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    return embed

# ================== READY ===================
@bot.event
async def on_ready():
    print("===================================")
    print(f"Bot Online: {bot.user}")
    print("===================================")
    if not hourly_loop.is_running():
        hourly_loop.start()
        print("✅ hourly_loop started")
# =========== embed แจ้งเตือน/คนส่งลิ้งก์ ===========
def create_payment_embed(member, amount, role, link=None, status="SUCCESS"):
    color = 0x00ff00 if status == "SUCCESS" else 0xff0000

    embed = discord.Embed(
        title="🧧 มีการส่งลิงก์อั่งเปา ",
        color=color
    )
    embed.set_author(
        name=f"{member.display_name}",
        icon_url=member.display_avatar.url
    )
    embed.set_thumbnail(url=member.display_avatar.url)

    embed.add_field(name="👤 ผู้ใช้", value=member.mention, inline=True)
    embed.add_field(name="💰 ราคา", value=f"{amount} บาท", inline=True)
    embed.add_field(name="🎭 ยศ", value=role.mention, inline=True)

    if link:
        embed.add_field(name="🔗 ลิ้งก์อั่งเปา", value=link, inline=False)

    embed.add_field(
        name="📥 สถานะ",
        value="✅  รับเงินแล้ว และให้ยศแล้ว" if status == "SUCCESS" else "❌ รับเงินไม่ได้",
        inline=False
    )

    embed.set_footer(text="Payment System")

    return embed
# ============= backend price ================
PRICE_ROLE_MAP = {
    149.0: ROLE_01,
    79.0: ROLE_02,
    50.0: ROLE_03,
    30.0: ROLE_04
}
# ================ กัน LINK ซ้ำ ===================
def load_links():

        if not os.path.exists("links.json"):
            return set()

        try:
            with open("links.json") as f:
                return set(json.load(f))
        except (json.JSONDecodeError, ValueError):
                return set()

def save_links():
    with open("links.json", "w") as f:
        json.dump(list(used_links), f)

used_links = load_links()       # ใช้แล้วจริง (backend เท่านั้น)
submitted_links = set()         # เคยส่ง (frontend)
# =========================
# ตรวจลิงก์ TrueWallet
# =========================
def is_valid_angpao(link: str) -> bool:
    link = link.strip().replace("<", "").replace(">", "")
    return "gift.truemoney.com" in link
# ==================================================
#  Model กรอกลิ้งก์ + หากกรอกลิ้งก์ถูกหรือผิด + แจ้งเตือนมีคนส่งลิ้งก์อั่งเปา
# ==================================================

class AngpaoModal(discord.ui.Modal, title="( กรุณากรอกลิงก์ซองอั่งเปา )"):

    def __init__(self, role_id):
        super().__init__()
        self.role_id = role_id

    link = discord.ui.TextInput(
        label="( 🧧 กรอกลิ้งก์ซองอั่งเปา )",
        placeholder="https://gift.truemoney.com/campaign/?v=xxxxxxxxxxxxxxxxxx",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:

        user_id = interaction.user.id
        now = datetime.datetime.now().timestamp()

        if user_id in cooldown and now - cooldown[user_id] < 10:
            remaining = int(10 - (now - cooldown[user_id]))
            timestamp = int(datetime.datetime.now().timestamp()) + remaining

            embed = discord.Embed(
                title="⏳ กรุณารอเวลาก่อนส่งใหม่",
                description=f"คุณสามารถส่งใหม่ได้อีกครั้งใน <t:{timestamp}:R>",
                color=discord.Color.orange()
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        cooldown[user_id] = now

        link_value = self.link.value.strip().replace("<", "").replace(">", "")

        # ===== loading =====
        await interaction.response.defer(ephemeral=True)

        msg = await interaction.followup.send(
            content="<a:main_loading:1486624902739005450>   **กำลังตรวจสอบลิ้งก์** โปรดรอสักครู่...",
            ephemeral=True
        )

        # ===== ตรวจ format =====
        print("🔍 BOT VALID:", link_value, is_valid_angpao(link_value))
        if not is_valid_angpao(link_value):
            embed = discord.Embed(
                title="`❌` กรุณากรอกลิงค์ที่อยู่ซองอั่งเปาให้ถูกต้อง!!",
                color=discord.Color.red()
            )
            await msg.edit(content=None, embed=embed)
            return

        # ===== ลิ้งซ้ำ =====
        if link_value in submitted_links:
            embed = discord.Embed(
                title="`❌` ลิ้งก์นี้เคยถูกส่งไปในระบบแล้ว",
                description="**```หากคุณกำลังประสบปัญหาซื้อไปแล้วแต่ไม่ได้ยศโปรดติดต่อแอดมินโดยด่วนครับ!```**",
                color=discord.Color.red()
            )
            await msg.edit(content=None, embed=embed)
            return

        # ❗ กัน spam กดหลายครั้งก่อนจบ
        if user_id in pending_links:
            embed = discord.Embed(
                title="`⏳` คุณมีรายการที่กำลังดำเนินการอยู่",
                description="**```กรุณารอให้รายการก่อนหน้าสำเร็จก่อน```**",
                color=discord.Color.orange()
            )
            await msg.edit(content=None, embed=embed)
            return

        pending_links[user_id] = link_value
        submitted_links.add(link_value)

        # ===== ยิง backend =====
        try:
            print("🔥 USING TIMEOUT 60")
            res = await asyncio.to_thread(
                requests.post,
                "https://discordrolebotbackend-production-baee.up.railway.app/redeem",
                json={
                    "user_id": user_id,
                    "link": link_value
                },
                timeout=60
            )

            if res.status_code != 200:
                pending_links.pop(user_id, None)
                submitted_links.discard(link_value)

                embed = discord.Embed(
                    title=f"`❌` ระบบมีปัญหาชั่วคราวโปรดลองใหม่อีกครั้งหรือแจ้งแอดมิน ({res.status_code})",
                    color=discord.Color.red()
                )
                await msg.edit(content=None, embed=embed)
                return

            # ===== ตรวจสถานะ =====
            try:
                data = res.json()
            except ValueError:
                pending_links.pop(user_id, None)
                submitted_links.discard(link_value)
                embed = discord.Embed(
                    title="`❌` ระบบเกิดข้อผิดพลาด กรุณาแจ้งแอดมิน",
                    color=discord.Color.red()
                )
                await msg.edit(content=None, embed=embed)
                return

            success = data.get("success")

            if not success:
                pending_links.pop(user_id, None)
                submitted_links.discard(link_value)

                error = data.get("error")

                if error == "invalid":
                    embed = discord.Embed(
                        title="`❌` กรุณากรอกลิงค์ที่อยู่ซองอั่งเปาให้ถูกต้อง!!",
                        color=discord.Color.red()
                    )
                    await msg.edit(content=None, embed=embed)
                    return

                if error == "used":
                    embed = discord.Embed(
                        title="`❌` ลิ้งก์ในซองนี้ถูกใช้ไปแล้ว 😓",
                        color=discord.Color.red()
                    )
                    await msg.edit(content=None, embed=embed)
                    return

                if error == "expired":
                    embed = discord.Embed(
                        title="`❌` ลิ้งก์อั่งเปานี้หมดอายุไปแล้ว",
                        color=discord.Color.red()
                    )
                    await msg.edit(content=None, embed=embed)
                    return

                if error == "processing":
                    embed = discord.Embed(
                        title="`⏳` มีคนกำลังซื้อยศอยู่จำนวนมาก",
                        description="**```กรุณารอสักครู่แล้วลองใหม่อีกครั้ง```**",
                        color=discord.Color.orange()
                    )
                    await msg.edit(content=None, embed=embed)
                    return

                embed = discord.Embed(
                    title=f"`❌` ไม่พบลิ้งก์ซองนี้ในระบบ {error}",
                    color=discord.Color.red()
                )
                await msg.edit(content=None, embed=embed)
                return


        except requests.exceptions.RequestException as e:
            pending_links.pop(user_id, None)
            submitted_links.discard(link_value)
            print("❌ BOT ERROR:", e)
            embed = discord.Embed(
                title=f"`❌` เชื่อมต่อไม่ได้: {e}",
                color=discord.Color.red()
            )
            await msg.edit(content=None, embed=embed)
            return

        except Exception as e:
            pending_links.pop(user_id, None)
            submitted_links.discard(link_value)
            embed = discord.Embed(
                title="`❌` เกิดข้อผิดพลาดบางอย่าง",
                color=discord.Color.red()
            )
            await msg.edit(content=None, embed=embed)
            print("ERROR:", e)
            return

        # ✅ SUCCESS
        amount = data.get("amount")

        # 🔥 DEBUG
        print(f"💰 amount จาก backend: {amount}")
        print(f"💰 keys ในระบบ: {list(PRICE_ROLE_MAP.keys())}")

        # 🔥 FIX float
        amount = float(amount)

        # 🔥 หา role ที่ "ถูกที่สุดที่ user เลือกได้"
        selected_price = None
        for price in sorted(PRICE_ROLE_MAP.keys()):
            if amount >= price:
                selected_price = price

        if selected_price is None:
            role_id = None
        else:
            role_id = PRICE_ROLE_MAP[selected_price]

        # DEBUG
        print(f"💰 amount: {amount}")
        print(f"💰 selected_price: {selected_price}")

        if not role_id:
            embed = discord.Embed(
                title="`❌` ราคาในซองไม่ตรงกับที่เลือก!!",
                color=discord.Color.red()
            )
            await msg.edit(content=None, embed=embed)
            return

        role = interaction.guild.get_role(role_id)

        member = interaction.user

        if role in member.roles:
            embed = discord.Embed(
                title="`❌` คุณมียศนี้อยู่แล้ว",
                color=discord.Color.red()
            )
            await msg.edit(content=None, embed=embed)
            return

        # ❗ กัน amount แปลก
        if amount <= 0:
            embed = discord.Embed(
                title="`❌` จำนวนเงินไม่ถูกต้อง",
                color=discord.Color.red()
            )
            await msg.edit(content=None, embed=embed)
            return

        # ❗ กัน spam / link ค้าง
        if user_id not in pending_links:
            embed = discord.Embed(
                title="`❌` ไม่พบลิ้งที่กำลังดำเนินการ",
                color=discord.Color.red()
            )
            await msg.edit(content=None, embed=embed)
            return
        # ถ้า role ที่ให้อยู่สูงกว่า = ให้ยศไม่สำเร็จ
        if role >= interaction.guild.me.top_role:
            print("❌ role สูงเกิน")
            await interaction.followup.send(
                embed=discord.Embed(
                    title="`❌` ให้ยศไม่สำเร็จ กรุณาติดต่อแอดมิน",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return
        # ถ้าเงินมาแต่ให้ยศไม่ได้ = fail
        try:
            await member.add_roles(role)
        except Exception as e:
            pending_links.pop(user_id, None)
            submitted_links.discard(link_value)
            print("❌ ให้ role ไม่สำเร็จ:", e)
            await interaction.followup.send(
                embed=discord.Embed(
                    title="`❌` ระบบมีปัญหา กรุณาติดต่อแอดมิน",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return

        # ✅ บันทึกลิ้งก์ + กันลิ้งก์ซ้ำ (หลังให้ role สำเร็จ)
        used_links.add(link_value)
        save_links()
        # ✅ ลบจาก submitted (กันค้าง)
        submitted_links.discard(link_value)

        pending_links.pop(user_id, None)

        # ✅ embed
        embed = discord.Embed(
            title="`✅` ซื้อยศสำเร็จ!!",
            description=f"คุณได้รับ {role.mention} แล้ว!\n\n```หากไม่ได้รับยศภายใน 10 วินาที กรุณาแจ้งแอดมิน```",
            color=discord.Color.green()
        )

        await msg.edit(content=None, embed=embed)

        # ✅ success channel
        angpao_channel = bot.get_channel(ANGPAO_CHANNEL_ID)

        embed = create_payment_embed(member, amount, role, link_value)

        if angpao_channel:
            await angpao_channel.send(
                content=f"📢 แจ้งเตือนถึง <@{OWNER_ID}>",
                embed=embed
            )
# ==================================================
#  Dropdown ช่องทางเติมเงิน (ตัวเลือก)
# ==================================================

class PaymentSelect(discord.ui.Select):

    def __init__(self):

        options = [
            discord.SelectOption(
                label="True Wallet",
                description="ซื้อด้วยซองอั่งเปา True Wallet",
                emoji=discord.PartialEmoji(name="angpao", id=1472134389763932350, animated=True)
            ),
            discord.SelectOption(
                label="PromptPay",
                description="ซื้อผ่านสแกน QR พร้อมเพย์ (ยังไม่เปิดใช้งาน!!)",
                emoji=discord.PartialEmoji(name="promtpay", id=1472134870368124998)
            ),
        ]

        super().__init__(
            placeholder="[ 🛒 เลือกช่องทางการเติมเงิน ]",
            options=options
        )

    async def callback(self, interaction: discord.Interaction):

        choice = self.values[0]

        if choice == "True Wallet":
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="ꔛ เลือกยศและราคาที่ต้องการซื้อ ꔛ",
                    description="เลือกยศที่ต้องการซื้อผ่านซองอั่งเปา",
                    color=0x5C67ED
                ),
                view=RoleSelectView(),
                ephemeral=True
            )

        elif choice == "PromptPay":
            embed = discord.Embed(
                title="`❌` **ช่องทาง __PromptPay__ ยังไม่เปิดใช้งาน**:pray:",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

class PaymentView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(PaymentSelect())

# ==================================================
#  RoleSelectView (เลือกราคาและบทบาท)
# ==================================================

ROLE_PRICES = {
    ROLE_01: 149.00,
    ROLE_02: 79.00,
    ROLE_03: 50.00,
    ROLE_04: 30.00
}

class RoleSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="𝐕𝐈𝐏・เห็นทุกห้อง + กลุ่มแรร์ๆ ꒰149บาท꒱",
                value=str(ROLE_01),
                description="ราคา 149.-",
                emoji=discord.PartialEmoji(name="star_1", id=1472134208993497202, animated=True)
            ),
            discord.SelectOption(
                label="𝐕𝐈𝐏・นานาชาติ ꒰79บาท꒱",
                value=str(ROLE_02),
                description="ราคา 79.-",
                emoji=discord.PartialEmoji(name="star_1", id=1472134208993497202, animated=True)
            ),
            discord.SelectOption(
                label="𝐕𝐈𝐏・𝑶𝒏𝒍𝒚𝒇𝒂𝒏𝒔 ꒰50บาท꒱",
                value=str(ROLE_03),
                description="ราคา 50.-",
                emoji=discord.PartialEmoji(name="star_1", id=1472134208993497202, animated=True)
            ),
            discord.SelectOption(
                label="𝐕𝐈𝐏・H/ANIME ꒰30บาท꒱",
                value=str(ROLE_04),
                description="ราคา 30.-",
                emoji=discord.PartialEmoji(name="star_1", id=1472134208993497202, animated=True)
            ),
        ]

        super().__init__(
            placeholder="[ 🛒 เลือกประเภทยศและราคา ]",
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        role_id = int(self.values[0])
        price = ROLE_PRICES.get(role_id, 0)

        embed = discord.Embed(
            title="<a:angpao:1472134389763932350> เติมด้วยซองอั่งเปา",
            description="กรุณากดยืนยันการซื้อก่อนดำเนินการต่อ",
            color=0x5C67ED
        )

        embed.add_field(
            name="`💰` ราคายศที่ยืนยัน",
            value=f"```{price:.2f} THB```",
            inline=False
        )

        await interaction.response.send_message(
            embed=embed,
            view=ConfirmView(role_id),
            ephemeral=True
        )

# ==================================================
#  ConfirmView (ปุ่มยืนยัน/ยกเลิก)
# ==================================================

class RoleSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(RoleSelect())

class ConfirmView(discord.ui.View):
    def __init__(self, role_id):
        super().__init__(timeout=None)
        self.role_id = role_id

    @discord.ui.button(label="ยืนยันการซื้อ", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, _):
        await interaction.response.send_modal(AngpaoModal(self.role_id))

    @discord.ui.button(label="ยกเลิก", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, _):
        embed = discord.Embed(
            title="`❌` ยกเลิกคำสั่งซื้อแล้ว",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(content=None, embed=embed, view=None)

# ==================================================
#  PriceView (ปุ่มซื้อยศ/ปิดหน้าต่าง)
# ==================================================
class PriceView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(
        label="ซื้อด้วยอั่งเปา",
        emoji=discord.PartialEmoji(name="truewallet_icon", id=1484455894283714701),
        style=discord.ButtonStyle.success
    )
    async def buy(self, interaction: discord.Interaction, _):
        embed = discord.Embed(
            title="ꔛ เลือกช่องทางเติมเงิน ꔛ",
            color=0x5C67ED
        )

        embed.set_image(
            url="https://images-ext-1.discordapp.net/external/xirWF0Vb4xRr7eX30asFDva_pZJAKltrQlBE3S8BOKo/https/img2.pic.in.th/pic/ds.png"
        )

        await interaction.response.send_message(
            embed=embed,
            view=PaymentView(),
            ephemeral=True
        )

    @discord.ui.button(
        label="ปิดหน้าต่าง",
        style=discord.ButtonStyle.secondary
    )
    async def close(self, interaction: discord.Interaction, _):

        embed = discord.Embed(
            title="ปิดหน้าต่างเรียบร้อยแล้ว",
            color=discord.Color.dark_grey()
        )

        await interaction.response.edit_message(
            content=None,
            embed=embed,
            view=None
        )

# ==================================================
#  View เมนูหลัก (ปุ่มซื้อ + เลือกช่องทางเติมเงิน)
# ==================================================

class MainView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="ซื้อด้วยอั่งเปา",
        emoji=discord.PartialEmoji(name="truewallet_icon", id=1484455894283714701),
        style=discord.ButtonStyle.green
    )
    async def topup(self, interaction: discord.Interaction, _):

        embed = discord.Embed(
            title="ꔛ เลือกช่องทางเติมเงิน ꔛ",
            color=0x5C67ED
        )

        embed.set_image(
            url="https://images-ext-1.discordapp.net/external/xirWF0Vb4xRr7eX30asFDva_pZJAKltrQlBE3S8BOKo/https/img2.pic.in.th/pic/ds.png?format=webp&quality=lossless"
        )

        await interaction.response.send_message(
            embed=embed,
            view=PaymentView(),
            ephemeral=True
        )


    @discord.ui.button(
        label="ดูราคายศ",
        emoji="🛒",
        style=discord.ButtonStyle.primary
    )
    async def rank_info(self, interaction: discord.Interaction, _):

        embed = discord.Embed(
            title="⋆｡˚୨🛒・ราคายศทั้งหมด୧˚｡⋆",
            description=(
                "**‧˚꒷꒦︶︶꒷︶︶꒷︶+꒷︶꒷꒦︶︶꒷︶︶₊꒷**\n"
                "**🛒 ซื้อยศ 149.- จะได้รับ**\n"
                "<a:star1:1472134208993497202> <@&1082885961953853540>\n\n"
                
                "**‧˚꒷꒦︶︶꒷︶︶꒷︶+꒷︶꒷꒦︶︶꒷︶︶₊꒷**\n"
                "**🛒 ซื้อยศ 79.- จะได้รับ**\n"
                "<a:star1:1472134208993497202> <@&1082668970718527508>\n\n"
                
                "**‧˚꒷꒦︶︶꒷︶︶꒷︶+꒷︶꒷꒦︶︶꒷︶︶₊꒷**\n"
                "**🛒 ซื้อยศ 50.- จะได้รับ**\n"
                "<a:star1:1472134208993497202> <@&1082667309254054008>\n\n"
                
                "**‧˚꒷꒦︶︶꒷︶︶꒷︶+꒷︶꒷꒦︶︶꒷︶︶₊꒷**\n"
                "**🛒 ซื้อยศ 30.- จะได้รับ**\n"
                "<a:star1:1472134208993497202> <@&1082667313163157515>\n\n"
                
                "**‧˚꒷꒦︶︶꒷︶︶꒷︶+꒷︶꒷꒦︶︶꒷︶︶₊꒷**"
            ),
            color=0x5C67ED
        )

        embed.set_footer(
            text="🧧 ชำระผ่านซองอั่งเปา TrueWallet เท่านั้น"
        )

        await interaction.response.send_message(
            embed=embed,
            view=PriceView(),
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions(roles=True)
        )

# ==================================================
#  embed ซื้อยศสำเร็จ (ส่วนของ ระบบอั่งเปา)
# ==================================================
@bot.command()
async def testembedsuccess(ctx):
    role = ctx.guild.get_role(ROLE_01)
    await send_purchase_success(ctx.author, role, bot.user)

async def send_purchase_success(member: discord.Member, role: discord.Role, giver):
    channel = bot.get_channel(SUCCESS_CHANNEL_ID)
    if channel is None:
        return

    # ====== เวลาไทย ======
    thai_tz = pytz.timezone("Asia/Bangkok")
    now = datetime.datetime.now(thai_tz).strftime("%d/%m/%Y %H:%M")

    embed = create_base_embed(
        "<a:correct3:1472134441248751788>  __ซื้อยศสำเร็จเรียบร้อยแล้ว!__  <a:bell_2:1472134346449354844>",
        member
    )

    embed.set_author(
        name=f"{member.display_name}",
        icon_url=member.display_avatar.url
    )

    embed.add_field(
        name=" ",
        value=f"`👤 ผู้ใช้ :` {member.mention}",
        inline=False
    )

    embed.add_field(
        name=" ",
        value=f"`🏅 ได้รับยศ :` {role.mention}",
        inline=False
    )

    if giver:
        embed.add_field(
            name=" ",
            value=f"`👮 ให้โดย :` {giver.mention}",
            inline=False
        )

    embed.add_field(
        name=" ",
        value=f" ",
        inline=False
    )

    embed.set_image(
        url="https://i.postimg.cc/3JkfNzdk/standard.gif"
    )

    guild = member.guild
    embed.set_footer(
        text=f"{guild.name} • {now}",
        icon_url=guild.icon.url if guild.icon else None
    )

    msg = await channel.send(embed=embed)
    await msg.add_reaction("✅")

# ==================================================
#  คำสั่งเปิดร้าน !shop
# ==================================================

@bot.command()
async def shop(ctx):

    if ctx.author.id != OWNER_ID:
        return
    # title อั่งเปา
    embed = discord.Embed(
        title=" <a:bowl_pink:1484474337061765122> 𝐀𝐔𝐓𝐎 𝐁𝐔𝐘 𝐑𝐎𝐋𝐄 <a:bowl_pink:1484474337061765122>  (ชำระผ่านทรูวอเล็ทเท่านั้น)",
        description="> **<a:angpao:1472134389763932350> ระบบซื้อยศอัตโนมัติ [24 ชั่วโมง] ✨** ",
        color=discord.Color.red()
    )
    # Gif บน embed อั่งเปา
    embed.set_image(
        url="https://i.pinimg.com/originals/b8/73/46/b873460b260b5cf96e3fe9a734799bb1.gif"
    )
    # ข้อความข้างล่าง embed อั่งเปา + ไอคอนเซิร์ฟซ้ายล่าง
    embed.set_footer(
        text="✅ ชำระผ่านซองอั่งเปายศเข้าตัวทันที 🔞",
        icon_url="https://media.discordapp.net/attachments/1478973402629935206/1483340274594877501/DOHEE_icon_png.png?ex=69be3048&is=69bcdec8&hm=c4674a41bb839e0f49652f7a00f2fcd78eaffb7ed418224d6e75e21a5e4a2368&=&format=webp&quality=lossless"
    )

    await ctx.send(embed=embed, view=MainView())
# ==================================================
#  ระบบให้ยศขึ้น embed ซื้อสำเร็จ
# ==================================================

@bot.event
async def on_member_update(before, after):
    # เช็ค role ที่เพิ่มเข้ามา
    added_roles = [r for r in after.roles if r not in before.roles]

    target_roles = [ROLE_01, ROLE_02, ROLE_03, ROLE_04]

    for role in added_roles:
        if role.id in target_roles:

            # หาใครเป็นคนให้ (จาก audit log)
            giver = None
            async for entry in after.guild.audit_logs(
                limit=5,
                action=discord.AuditLogAction.member_role_update
            ):
                if entry.target.id == after.id:
                    giver = entry.user
                    break

            # ถ้าไม่เจอ ให้เป็นคุณ (OWNER)
            if giver is None:
                giver = bot.get_user(OWNER_ID)

            await send_purchase_success(after, role, giver)

# ==================================================
#  ระบบส่งข้อความลูปทุกๆ 1 ชั่วโมง (ระบบอั่งเปา)
# ==================================================

@bot.command()
async def testloop(ctx):
    await ctx.send("ทดสอบระบบลูป...")
    await hourly_loop()

last_messages = []

@tasks.loop(minutes=1)
async def hourly_loop():

    print("⏰ loop tick:")
    thai_tz = pytz.timezone("Asia/Bangkok")
    now = datetime.datetime.now(thai_tz)

    # เช็คว่าเป็นต้นชั่วโมงไหม (นาที = 0)
    if now.minute != 0:
        return

    channel = bot.get_channel(LOG_CHANNEL_ID)
    if channel is None:
        return

    global last_messages

    # ลบข้อความเก่า
    for msg in last_messages:
        try:
            await msg.delete()
        except discord.NotFound:
            pass
        except discord.Forbidden:
            pass

    last_messages = []

    # ข้อความที่ 1
    msg1 = await channel.send("""
    # <a:star_1:1472134208993497202> วิธีการซื้อ <a:star_1:1472134208993497202>
    ### <a:correct2:1472846699495034981> ขั้นตอนที่ 1 : เข้า "__TrueWallet__" กดสร้างซองอั่งเปาใส่ราคาตามยศนั้นๆ <:truewallet:1472134849019248782>
    ### <a:correct2:1472846699495034981> ขั้นตอนที่ 2 : นำลิงก์ซองอั่งเปามาใส่ใน "__ซื้อด้วยอั่งเปา__" ได้เลยครับ! <a:angpao:1472134389763932350>
    > **<a:flower8:1472928911594885142> เช็คการซื้อยศสำเร็จได้ที่ <a:flower8:1472928911594885142>**
    ** <a:correct3:1472134441248751788> <#1470997698004914197> <a:vip1:1472132052026527754>**
    ||@everyone|| ||@everyone||
    """)

    # ข้อความที่ 2 (รูป GIF 1 รูป)
    gif1 = await channel.send("https://i.postimg.cc/7Lt8PrZM/rainbow-water-falling.gif")
    last_messages = [msg1, gif1]
# ================ TEST BOT ==================
@bot.command()
async def ping(ctx):
    await ctx.send("pong")
# ================= RUN =================
server_on()
bot.run(os.getenv('TOKEN'))

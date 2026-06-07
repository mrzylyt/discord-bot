import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
import asyncio
from datetime import datetime, timedelta
import json
import os

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
TOKEN = os.environ.get("TOKEN")

SALON_COMMANDE_ID   = 1512563280919400628
SALON_TABLEAU_ID    = 1512563357314715754
SALON_PLANNING_ID   = 1512563459278241822
TON_ID              = 1000860625968320604
CATEGORY_CLIENTS_ID  = 1512563641512362084
SALON_REGLEMENT_ID   = 1512823100394176543
ROLE_NON_VERIFIE_ID  = 1513146382830141592
SALON_PAIEMENTS_ID  = 1512828613207134401

PAYPAL_EMAIL = "mrzylyt@gmail.com"

PRIX_MINIATURE_UNITAIRE = 25
PRIX_MINI_PACK_4        = 99
PRIX_MINI_PACK_8        = 179
PRIX_MONTAGE_PAR_MINUTE = 3

DATA_FILE = "commandes.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ─────────────────────────────────────────────
#  MENU CLIENT (boutons persistants)
# ─────────────────────────────────────────────

class BoutonReglement(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="✅  J'accepte le règlement", style=discord.ButtonStyle.success, custom_id="accepter_reglement")
    async def accepter(self, interaction: discord.Interaction, button: Button):
        guild  = interaction.guild or bot.get_guild(interaction.guild_id)
        member = guild.get_member(interaction.user.id)
        role   = guild.get_role(ROLE_NON_VERIFIE_ID)

        if role and role in member.roles:
            await member.remove_roles(role, reason="Règlement accepté")
            await interaction.response.send_message(
                "✅ Merci d'avoir accepté le règlement ! Tu as maintenant accès au serveur. Bienvenue ! 🎉",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "✅ Tu as déjà accepté le règlement !",
                ephemeral=True
            )


class MenuCommande(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎨  Miniature", style=discord.ButtonStyle.primary, custom_id="menu_miniature")
    async def miniature(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(ModalMiniature())

    @discord.ui.button(label="🎬  Montage vidéo", style=discord.ButtonStyle.secondary, custom_id="menu_montage")
    async def montage(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(ModalMontage())


class ModalMiniature(Modal, title="Commander une Miniature"):
    nom_chaine  = TextInput(label="Nom de ta chaîne YouTube", placeholder="Ex: LeoProd")
    description = TextInput(label="Description / style souhaité", placeholder="Ex: fond sombre, titre rouge…", style=discord.TextStyle.paragraph)
    pack        = TextInput(label="Pack (unitaire / pack4 / pack8)", placeholder="unitaire=25€ | pack4=99€/mois | pack8=179€/mois")

    async def on_submit(self, interaction: discord.Interaction):
        p = self.pack.value.strip().lower()
        if "8" in p:
            prix, label = PRIX_MINI_PACK_8, f"{PRIX_MINI_PACK_8}€/mois (pack 8 miniatures)"
        elif "4" in p:
            prix, label = PRIX_MINI_PACK_4, f"{PRIX_MINI_PACK_4}€/mois (pack 4 miniatures)"
        else:
            prix, label = PRIX_MINIATURE_UNITAIRE, f"{PRIX_MINIATURE_UNITAIRE}€ (unitaire)"
        await creer_commande(interaction, "Miniature", self.nom_chaine.value, self.description.value, prix, label)


class ModalMontage(Modal, title="Commander un Montage Vidéo"):
    nom_chaine  = TextInput(label="Nom de ta chaîne YouTube", placeholder="Ex: LeoProd")
    duree       = TextInput(label="Durée estimée de la vidéo finale (minutes)", placeholder="Ex: 10")
    description = TextInput(label="Description / style souhaité", placeholder="Ex: transitions dynamiques…", style=discord.TextStyle.paragraph)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            duree_min = float(self.duree.value.strip().replace(",", "."))
        except ValueError:
            await interaction.response.send_message("❌ Durée invalide, entre un nombre (ex: 10).", ephemeral=True)
            return
        prix  = round(duree_min * PRIX_MONTAGE_PAR_MINUTE, 2)
        label = f"{prix}€ ({duree_min} min × {PRIX_MONTAGE_PAR_MINUTE}€/min)"
        await creer_commande(interaction, "Montage", self.nom_chaine.value, self.description.value, prix, label, duree=duree_min)


# ─────────────────────────────────────────────
#  BOUTONS GESTION (dans #tableau-commandes)
#  Le custom_id contient l'ID de la commande
# ─────────────────────────────────────────────

class BoutonsGestion(View):
    """Boutons affichés sous chaque commande dans le tableau privé."""
    def __init__(self, commande_id: str):
        super().__init__(timeout=None)
        self.commande_id = commande_id
        # Bouton "Définir prix & délai"
        btn_prix = Button(
            label="💰 Prix & Délai",
            style=discord.ButtonStyle.success,
            custom_id=f"gestion_prix_{commande_id}"
        )
        btn_prix.callback = self.definir_prix
        self.add_item(btn_prix)
        # Bouton "Marquer terminé"
        btn_done = Button(
            label="✅ Terminé",
            style=discord.ButtonStyle.primary,
            custom_id=f"gestion_done_{commande_id}"
        )
        btn_done.callback = self.marquer_termine
        self.add_item(btn_done)
        # Bouton "Annuler"
        btn_cancel = Button(
            label="❌ Annuler",
            style=discord.ButtonStyle.danger,
            custom_id=f"gestion_cancel_{commande_id}"
        )
        btn_cancel.callback = self.annuler
        self.add_item(btn_cancel)
        # Bouton "Fermer salon"
        btn_fermer = Button(
            label="🔒 Fermer salon",
            style=discord.ButtonStyle.secondary,
            custom_id=f"gestion_fermer_{commande_id}"
        )
        btn_fermer.callback = self.fermer_salon
        self.add_item(btn_fermer)
        # Bouton "Acompte reçu"
        btn_acompte = Button(
            label="💳 Acompte reçu",
            style=discord.ButtonStyle.success,
            custom_id=f"gestion_acompte_{commande_id}"
        )
        btn_acompte.callback = self.acompte_recu
        self.add_item(btn_acompte)
        # Bouton "Paiement final reçu"
        btn_final = Button(
            label="💵 Paiement final reçu",
            style=discord.ButtonStyle.success,
            custom_id=f"gestion_final_{commande_id}"
        )
        btn_final.callback = self.paiement_final
        self.add_item(btn_final)

    async def definir_prix(self, interaction: discord.Interaction):
        if interaction.user.id != TON_ID:
            await interaction.response.send_message("❌ Réservé au créateur.", ephemeral=True)
            return
        await interaction.response.send_modal(ModalPrixDelai(self.commande_id))

    async def marquer_termine(self, interaction: discord.Interaction):
        if interaction.user.id != TON_ID:
            await interaction.response.send_message("❌ Réservé au créateur.", ephemeral=True)
            return
        await action_statut(interaction, self.commande_id, "✅ Terminé")

    async def annuler(self, interaction: discord.Interaction):
        if interaction.user.id != TON_ID:
            await interaction.response.send_message("❌ Réservé au créateur.", ephemeral=True)
            return
        await action_statut(interaction, self.commande_id, "❌ Annulé")

    async def fermer_salon(self, interaction: discord.Interaction):
        if interaction.user.id != TON_ID:
            await interaction.response.send_message("❌ Réservé au créateur.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild or bot.get_guild(interaction.guild_id)
        await action_fermer(guild, self.commande_id)
        await interaction.followup.send(f"✅ Salon fermé.", ephemeral=True)

    async def acompte_recu(self, interaction: discord.Interaction):
        if interaction.user.id != TON_ID:
            await interaction.response.send_message("❌ Réservé au créateur.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild or bot.get_guild(interaction.guild_id)
        await action_paiement(guild, self.commande_id, "acompte")
        await interaction.followup.send("✅ Acompte enregistré !", ephemeral=True)

    async def paiement_final(self, interaction: discord.Interaction):
        if interaction.user.id != TON_ID:
            await interaction.response.send_message("❌ Réservé au créateur.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild or bot.get_guild(interaction.guild_id)
        await action_paiement(guild, self.commande_id, "final")
        await interaction.followup.send("✅ Paiement final enregistré !", ephemeral=True)


class ModalPrixDelai(Modal, title="Définir prix final & délai"):
    prix_final  = TextInput(label="Prix final (€)", placeholder="Ex: 25")
    delai_jours = TextInput(label="Délai de livraison (jours)", placeholder="Ex: 3")

    def __init__(self, commande_id: str):
        super().__init__()
        self.commande_id = commande_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            prix  = float(self.prix_final.value.strip().replace(",", "."))
            delai = int(self.delai_jours.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ Valeurs invalides.", ephemeral=True)
            return

        data = load_data()
        if self.commande_id not in data:
            await interaction.response.send_message("❌ Commande introuvable.", ephemeral=True)
            return

        commande = data[self.commande_id]
        commande["prix_final"]     = prix
        commande["delai_jours"]    = delai
        commande["statut"]         = "⏳ En cours"
        date_livraison             = datetime.now() + timedelta(days=delai)
        commande["date_livraison"] = date_livraison.strftime("%d/%m/%Y")
        save_data(data)

        await interaction.response.send_message(
            f"✅ Prix **{prix}€** et délai **{delai} jours** enregistrés !", ephemeral=True
        )
        # Récupère le guild via bot car interaction.guild peut être None depuis un modal
        guild = interaction.guild or bot.get_guild(interaction.guild_id)
        if guild:
            await maj_tableau(guild, data)
            await maj_planning(guild, data)
            await envoyer_message_client(guild, commande, prix, delai, date_livraison)


# ─────────────────────────────────────────────
#  ACTIONS PARTAGÉES
# ─────────────────────────────────────────────

async def action_statut(interaction, commande_id, nouveau_statut):
    data = load_data()
    if commande_id not in data:
        await interaction.response.send_message("❌ Commande introuvable.", ephemeral=True)
        return
    data[commande_id]["statut"] = nouveau_statut
    save_data(data)
    await interaction.response.send_message(f"✅ Statut → **{nouveau_statut}**", ephemeral=True)
    guild = interaction.guild or bot.get_guild(interaction.guild_id)
    await maj_tableau(guild, data)
    await maj_planning(guild, data)


async def action_fermer(guild, commande_id):
    data = load_data()
    if commande_id not in data:
        return
    commande     = data[commande_id]
    salon_client = bot.get_channel(commande["salon_client_id"]) if commande["salon_client_id"] else None
    if salon_client:
        client  = guild.get_member(commande["client_id"])
        mention = client.mention if client else "Client"
        embed   = discord.Embed(
            title="🔒 Commande clôturée",
            description="Cette commande est **terminée et archivée**.\nMerci pour ta confiance ! 🙏\n\n*Salon supprimé dans 10 secondes.*",
            color=discord.Color.dark_grey()
        )
        await salon_client.send(f"{mention}", embed=embed)
        await asyncio.sleep(10)
        await salon_client.delete(reason=f"Commande {commande_id} clôturée")
    data[commande_id]["statut"]          = "🔒 Clôturé"
    data[commande_id]["salon_client_id"] = None
    save_data(data)
    await maj_tableau(guild, data)
    await maj_planning(guild, data)


async def action_paiement(guild, commande_id, type_paiement):
    data = load_data()
    if commande_id not in data:
        return
    commande = data[commande_id]

    if type_paiement == "acompte":
        data[commande_id]["paiement"] = "✅ Acompte reçu"
        montant = round((commande["prix_final"] or commande["prix_estime"]) / 2, 2)
        label_paiement = f"Acompte — {montant}€"
        msg_client = "✅ Acompte reçu, ta commande est lancée ! 🚀"
    else:
        data[commande_id]["paiement"] = "✅ Payé intégralement"
        data[commande_id]["statut"]   = "✅ Terminé"
        montant = round((commande["prix_final"] or commande["prix_estime"]) / 2, 2)
        label_paiement = f"Paiement final — {montant}€"
        msg_client = "✅ Paiement final reçu, merci ! Le fichier arrive bientôt 🎁"

    save_data(data)

    # Notifier le client dans son salon
    salon_client = bot.get_channel(commande["salon_client_id"]) if commande["salon_client_id"] else None
    if salon_client:
        client  = guild.get_member(commande["client_id"])
        mention = client.mention if client else "Client"
        await salon_client.send(f"{mention} {msg_client}")

    # Log dans #paiements-reçus
    salon_paiements = guild.get_channel(SALON_PAIEMENTS_ID)
    if salon_paiements:
        embed = discord.Embed(
            title="💰 Paiement reçu",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.add_field(name="📦 Commande", value=f"`{commande_id}`",             inline=True)
        embed.add_field(name="🎨 Type",     value=commande["type"],               inline=True)
        embed.add_field(name="📺 Chaîne",   value=commande["nom_chaine"],         inline=True)
        embed.add_field(name="👤 Client",   value=f"<@{commande['client_id']}>",  inline=True)
        embed.add_field(name="💵 Montant",  value=f"**{montant}€**",              inline=True)
        embed.add_field(name="📋 Type",     value=label_paiement,                 inline=True)
        embed.set_footer(text=f"Reçu le {datetime.now().strftime('%d/%m/%Y à %H:%M')}")
        await salon_paiements.send(embed=embed)

    await maj_tableau(guild, data)
    await maj_planning(guild, data)


# ─────────────────────────────────────────────
#  CRÉER UNE COMMANDE
# ─────────────────────────────────────────────

async def creer_commande(interaction, type_commande, nom_chaine, description, prix, label_prix, duree=None):
    guild  = interaction.guild or bot.get_guild(interaction.guild_id)
    client = interaction.user

    commande_id = f"{type_commande[:4].upper()}-{int(datetime.now().timestamp())}"

    category = guild.get_channel(CATEGORY_CLIENTS_ID)
    moi      = guild.get_member(TON_ID)
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        client:             discord.PermissionOverwrite(read_messages=True, send_messages=True),
    }
    if moi:
        overwrites[moi] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

    salon_client = await guild.create_text_channel(
        name=f"commande-{nom_chaine.lower().replace(' ', '-')}",
        category=category,
        overwrites=overwrites
    )

    data = load_data()
    data[commande_id] = {
        "id":             commande_id,
        "type":           type_commande,
        "client_id":      client.id,
        "client_nom":     str(client),
        "nom_chaine":     nom_chaine,
        "description":    description,
        "prix_estime":    prix,
        "label_prix":     label_prix,
        "duree":          duree,
        "prix_final":     None,
        "delai_jours":    None,
        "date_livraison": None,
        "statut":         "🔔 Nouvelle",
        "salon_client_id": salon_client.id,
        "date_commande":  datetime.now().strftime("%d/%m/%Y %H:%M"),
        "paiement":       "⏳ En attente"
    }
    save_data(data)

    await interaction.response.send_message(
        f"✅ Commande **{type_commande}** reçue ! Retrouve les détails dans {salon_client.mention} 🎉",
        ephemeral=True
    )

    # Message dans le salon client
    embed_client = discord.Embed(title=f"📦 Commande {type_commande} — {commande_id}", color=discord.Color.blue())
    embed_client.add_field(name="👤 Client",       value=client.mention, inline=True)
    embed_client.add_field(name="📺 Chaîne",       value=nom_chaine,     inline=True)
    embed_client.add_field(name="💰 Tarif estimé", value=label_prix,     inline=True)
    embed_client.add_field(name="📝 Description",  value=description,    inline=False)
    embed_client.set_footer(text="Le créateur va confirmer le prix final et le délai !")
    await salon_client.send(f"Bonjour {client.mention} ! 👋", embed=embed_client)

    await maj_tableau(guild, data)


# ─────────────────────────────────────────────
#  TABLEAU & PLANNING
# ─────────────────────────────────────────────

async def maj_tableau(guild, data):
    salon = guild.get_channel(SALON_TABLEAU_ID)
    if not salon or not data:
        return

    async for msg in salon.history(limit=100):
        if msg.author == guild.me:
            await msg.delete()
            await asyncio.sleep(0.3)

    header = discord.Embed(
        title="📋 Tableau des commandes",
        description=f"**{len(data)} commande(s)** — clique sur les boutons pour gérer",
        color=discord.Color.dark_blue(),
        timestamp=datetime.now()
    )
    header.set_footer(text="Dernière mise à jour")
    await salon.send(embed=header)
    await asyncio.sleep(0.3)

    for cmd in data.values():
        prix_str  = f"{cmd['prix_final']}€" if cmd["prix_final"] else f"~{cmd['prix_estime']}€"
        livraison = cmd["date_livraison"] or "⏳ À définir"

        if cmd["statut"] == "✅ Terminé":
            color = discord.Color.green()
        elif cmd["statut"] in ("❌ Annulé", "🔒 Clôturé"):
            color = discord.Color.red()
        elif cmd["statut"] == "⏳ En cours":
            color = discord.Color.orange()
        else:
            color = discord.Color.blurple()

        embed = discord.Embed(
            title=f"{'🎨' if cmd['type'] == 'Miniature' else '🎬'} {cmd['type']} — `{cmd['id']}`",
            color=color,
            timestamp=datetime.now()
        )
        embed.add_field(name="👤 Client",      value=f"<@{cmd['client_id']}>",   inline=True)
        embed.add_field(name="📺 Chaîne",      value=cmd["nom_chaine"],           inline=True)
        embed.add_field(name="💰 Prix",        value=prix_str,                    inline=True)
        embed.add_field(name="📅 Livraison",   value=livraison,                   inline=True)
        embed.add_field(name="📌 Statut",      value=cmd["statut"],               inline=True)
        embed.add_field(name="💳 Paiement",    value=cmd["paiement"],             inline=True)
        embed.add_field(name="📝 Description", value=cmd["description"][:200],    inline=False)
        embed.set_footer(text=f"Commande le {cmd['date_commande']}")

        # Boutons seulement pour les commandes non clôturées
        if cmd["statut"] not in ("🔒 Clôturé", "❌ Annulé"):
            await salon.send(embed=embed, view=BoutonsGestion(cmd["id"]))
        else:
            await salon.send(embed=embed)
        await asyncio.sleep(0.3)


async def maj_planning(guild, data):
    salon = guild.get_channel(SALON_PLANNING_ID)
    if not salon:
        return

    actives = [c for c in data.values() if c["statut"] not in ("✅ Terminé", "❌ Annulé", "🔒 Clôturé") and c["date_livraison"]]
    actives.sort(key=lambda x: datetime.strptime(x["date_livraison"], "%d/%m/%Y"))

    embed = discord.Embed(title="📅 Planning de livraison", color=discord.Color.green(), timestamp=datetime.now())
    if not actives:
        embed.description = "*Aucune commande en cours.*"
    else:
        for cmd in actives:
            embed.add_field(
                name=f"🗓️ {cmd['date_livraison']} — {cmd['type']} ({cmd['id']})",
                value=(
                    f"👤 **Client :** <@{cmd['client_id']}>\n"
                    f"📺 **Chaîne :** {cmd['nom_chaine']}\n"
                    f"💰 **Prix :** {cmd['prix_final']}€\n"
                    f"📌 **Statut :** {cmd['statut']}\n"
                    f"💳 **Paiement :** {cmd['paiement']}"
                ),
                inline=False
            )
    embed.set_footer(text="Dernière mise à jour")

    async for msg in salon.history(limit=20):
        if msg.author == guild.me and msg.embeds and "Planning" in msg.embeds[0].title:
            await msg.edit(embed=embed)
            return
    await salon.send(embed=embed)


async def envoyer_message_client(guild, commande, prix, delai, date_livraison):
    salon = guild.get_channel(commande["salon_client_id"])
    if not salon:
        return
    acompte = round(prix / 2, 2)
    client  = guild.get_member(commande["client_id"])
    mention = client.mention if client else "Client"

    embed = discord.Embed(title="💰 Confirmation de ta commande", color=discord.Color.gold())
    embed.add_field(name="📦 Type",      value=commande["type"],                       inline=True)
    embed.add_field(name="💵 Total",     value=f"**{prix}€**",                         inline=True)
    embed.add_field(name="📅 Livraison", value=date_livraison.strftime("%d/%m/%Y"),    inline=True)
    embed.add_field(
        name="💳 Acompte à payer maintenant",
        value=f"**{acompte}€** (50% du total)\nSolde restant à la livraison : **{acompte}€**",
        inline=False
    )
    embed.add_field(
        name="📲 Paiement via PayPal",
        value=f"Envoie à **`{PAYPAL_EMAIL}`**\n> ⚠️ Choisis **\"Envoyer à un ami\"** pour éviter les frais\nConfirme ici une fois payé !",
        inline=False
    )
    embed.set_footer(text="Une fois l'acompte reçu, ta commande sera lancée 🚀")
    await salon.send(f"{mention} voici le récap de ta commande :", embed=embed)


# ─────────────────────────────────────────────
#  COMMANDES TEXTE
# ─────────────────────────────────────────────

def check_owner(ctx):
    return ctx.author.id == TON_ID


@bot.command()
async def setup(ctx):
    """!setup — Envoie le menu dans #commandes"""
    if not check_owner(ctx): return
    salon = bot.get_channel(SALON_COMMANDE_ID)
    if not salon:
        await ctx.send("❌ Salon commande introuvable.")
        return
    embed = discord.Embed(
        title="🎨 Studio Créatif — Commandez ici !",
        description=(
            "Bienvenue ! Choisis le service dont tu as besoin :\n\n"
            f"**🎨 Miniature YouTube**\n"
            f"• Unitaire : **{PRIX_MINIATURE_UNITAIRE}€**\n"
            f"• Pack 4/mois : **{PRIX_MINI_PACK_4}€/mois**\n"
            f"• Pack 8/mois : **{PRIX_MINI_PACK_8}€/mois**\n\n"
            f"**🎬 Montage Vidéo**\n"
            f"• **{PRIX_MONTAGE_PAR_MINUTE}€ / minute** de rendu final\n\n"
            "👇 Clique sur le bouton pour passer commande !"
        ),
        color=discord.Color.blurple()
    )
    embed.set_footer(text="Un salon privé sera créé pour suivre ta commande.")
    await salon.send(embed=embed, view=MenuCommande())
    await ctx.message.delete()


@bot.command()
async def prix(ctx, commande_id: str, prix_val: str, delai_val: str):
    """!prix COMMANDE_ID PRIX JOURS"""
    if not check_owner(ctx): return
    try:
        p = float(prix_val.replace(",", "."))
        d = int(delai_val)
    except ValueError:
        await ctx.send("❌ Usage : `!prix MINI-123 25 3`")
        return
    data = load_data()
    if commande_id not in data:
        await ctx.send(f"❌ Commande `{commande_id}` introuvable.")
        return
    commande = data[commande_id]
    commande["prix_final"]     = p
    commande["delai_jours"]    = d
    commande["statut"]         = "⏳ En cours"
    date_livraison             = datetime.now() + timedelta(days=d)
    commande["date_livraison"] = date_livraison.strftime("%d/%m/%Y")
    save_data(data)
    await ctx.send(f"✅ `{commande_id}` → **{p}€** | Livraison : **{date_livraison.strftime('%d/%m/%Y')}**")
    await maj_tableau(ctx.guild, data)
    await maj_planning(ctx.guild, data)
    await envoyer_message_client(ctx.guild, commande, p, d, date_livraison)


@bot.command()
async def livrer(ctx, commande_id: str):
    """!livrer COMMANDE_ID"""
    if not check_owner(ctx): return
    data = load_data()
    if commande_id not in data:
        await ctx.send("❌ Commande introuvable.")
        return
    commande = data[commande_id]
    salon    = bot.get_channel(commande["salon_client_id"])
    if not salon:
        await ctx.send("❌ Salon client introuvable.")
        return
    client  = ctx.guild.get_member(commande["client_id"])
    mention = client.mention if client else "Client"
    acompte = round((commande["prix_final"] or commande["prix_estime"]) / 2, 2)
    embed = discord.Embed(
        title="🎉 Ta commande est prête !",
        description=(
            f"Ton **{commande['type']}** est terminé !\n\n"
            f"💳 **Solde restant : {acompte}€**\n"
            f"Envoie via **PayPal** à `{PAYPAL_EMAIL}`\n"
            "> ⚠️ Choisis **\"Envoyer à un ami\"**\n\n"
            "Une fois payé, je t'envoie le fichier final ici 🎁"
        ),
        color=discord.Color.green()
    )
    await salon.send(f"{mention}", embed=embed)
    data[commande_id]["statut"] = "📬 Livraison en attente"
    save_data(data)
    await maj_tableau(ctx.guild, data)
    await maj_planning(ctx.guild, data)
    await ctx.send(f"✅ Message envoyé dans {salon.mention}")


@bot.command()
async def paiement(ctx, commande_id: str, type_paiement: str = "solde"):
    """!paiement COMMANDE_ID acompte|solde"""
    if not check_owner(ctx): return
    data = load_data()
    if commande_id not in data:
        await ctx.send("❌ Commande introuvable.")
        return
    if "acompte" in type_paiement.lower():
        data[commande_id]["paiement"] = "✅ Acompte reçu"
        msg = "Acompte enregistré !"
        msg_client = "✅ Acompte reçu, ta commande est lancée ! 🚀"
    else:
        data[commande_id]["paiement"] = "✅ Payé intégralement"
        data[commande_id]["statut"]   = "✅ Terminé"
        msg = "Paiement complet, commande terminée !"
        msg_client = "✅ Paiement complet reçu, merci ! Le fichier final arrive 🎁"
    save_data(data)
    salon_client = bot.get_channel(data[commande_id]["salon_client_id"]) if data[commande_id]["salon_client_id"] else None
    if salon_client:
        client  = ctx.guild.get_member(data[commande_id]["client_id"])
        mention = client.mention if client else "Client"
        await salon_client.send(f"{mention} {msg_client}")
    await maj_tableau(ctx.guild, data)
    await maj_planning(ctx.guild, data)
    await ctx.send(f"✅ {msg}")


@bot.command()
async def fermer(ctx, commande_id: str):
    """!fermer COMMANDE_ID — Supprime le salon client"""
    if not check_owner(ctx): return
    await action_fermer(ctx.guild, commande_id)
    await ctx.send(f"✅ Commande `{commande_id}` clôturée.")


@bot.command()
async def commandes(ctx):
    """!commandes — Liste toutes les commandes"""
    if not check_owner(ctx): return
    data = load_data()
    if not data:
        await ctx.send("Aucune commande pour l'instant.")
        return
    embed = discord.Embed(title="📋 Liste des commandes", color=discord.Color.blurple())
    for cmd in data.values():
        embed.add_field(
            name=f"`{cmd['id']}` — {cmd['type']}",
            value=f"📺 {cmd['nom_chaine']} | 📌 {cmd['statut']} | 💰 {cmd['prix_final'] or '~'+str(cmd['prix_estime'])}€",
            inline=False
        )
    embed.set_footer(text="!prix ID PRIX JOURS | !livrer ID | !paiement ID acompte/solde | !fermer ID")
    await ctx.send(embed=embed)


@bot.command()
async def reglement(ctx):
    """!reglement — Envoie le règlement avec bouton dans #règles"""
    if not check_owner(ctx): return
    salon = bot.get_channel(SALON_REGLEMENT_ID)
    if not salon:
        await ctx.send("❌ Salon règles introuvable.")
        return

    embed = discord.Embed(
        title="📋 Règlement du serveur",
        color=discord.Color.purple()
    )
    embed.description = "Bienvenue ! Avant d'accéder au serveur, lis et accepte les règles suivantes."
    embed.add_field(
        name="1️⃣ Respect",
        value="Sois respectueux envers tout le monde. Aucune insulte, discrimination ou harcèlement toléré.",
        inline=False
    )
    embed.add_field(
        name="2️⃣ Commandes",
        value="Toutes les commandes se font uniquement via <#1512563280919400628>. Ne contacte pas le créateur en DM pour commander.",
        inline=False
    )
    embed.add_field(
        name="3️⃣ Paiement",
        value="L'acompte (50%) doit être payé pour lancer la commande. Aucun remboursement une fois le travail commencé. Paiement via PayPal uniquement.",
        inline=False
    )
    embed.add_field(
        name="4️⃣ Délais",
        value="Les délais sont donnés à titre indicatif. Des modifications majeures en cours de route peuvent allonger le délai.",
        inline=False
    )
    embed.add_field(
        name="5️⃣ Droits",
        value="Le créateur peut utiliser les créations dans son portfolio. Le client obtient les droits d'utilisation sur sa chaîne YouTube.",
        inline=False
    )
    embed.add_field(
        name="6️⃣ Comportement",
        value="Pas de spam, pub ou contenu inapproprié. Restez dans les salons prévus à cet effet.",
        inline=False
    )
    embed.set_footer(text="En cliquant sur le bouton ci-dessous, tu acceptes ces règles.")
    await salon.send(embed=embed, view=BoutonReglement())
    await ctx.message.delete()


# ─────────────────────────────────────────────
#  EVENTS
# ─────────────────────────────────────────────

@bot.event
async def on_ready():
    print(f"✅ Bot connecté : {bot.user} ({bot.user.id})")
    bot.add_view(MenuCommande())
    bot.add_view(BoutonReglement())
    print("📋 Views persistantes chargées.")


bot.run(TOKEN)

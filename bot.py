import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput, Select
import asyncio
from datetime import datetime, timedelta
import json
import os

# ─────────────────────────────────────────────
#  CONFIG — modifie ces valeurs
# ─────────────────────────────────────────────
TOKEN = os.environ.get("TOKEN")

# IDs Discord
SALON_COMMANDE_ID   = 1512563280919400628   # #commandes
SALON_TABLEAU_ID    = 1512563357314715754   # #tableau-commandes (privé)
SALON_PLANNING_ID   = 1512563459278241822   # #planning (privé)
TON_ID              = 1000860625968320604   # Ton ID Discord
CATEGORY_CLIENTS_ID = 1512563641512362084  # Catégorie clients

# PayPal
PAYPAL_EMAIL = "mrzylyt@gmail.com"

# Tarifs
PRIX_MINIATURE_UNITAIRE   = 25
PRIX_MINI_PACK_4          = 99
PRIX_MINI_PACK_8          = 179
PRIX_MONTAGE_PAR_MINUTE   = 3

# ─────────────────────────────────────────────
#  STOCKAGE DES COMMANDES (fichier JSON simple)
# ─────────────────────────────────────────────
DATA_FILE = "commandes.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ─────────────────────────────────────────────
#  BOT SETUP
# ─────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ─────────────────────────────────────────────
#  VIEWS & MODALS
# ─────────────────────────────────────────────

class MenuCommande(View):
    """Boutons affichés dans #commandes"""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎨  Miniature", style=discord.ButtonStyle.primary, custom_id="btn_miniature")
    async def miniature(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(ModalMiniature())

    @discord.ui.button(label="🎬  Montage vidéo", style=discord.ButtonStyle.secondary, custom_id="btn_montage")
    async def montage(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(ModalMontage())


class ModalMiniature(Modal, title="Commander une Miniature"):
    nom_chaine = TextInput(label="Nom de ta chaîne YouTube", placeholder="Ex: LeoProd", required=True)
    description = TextInput(
        label="Description / style souhaité",
        placeholder="Ex: fond sombre, titre en rouge, style gaming…",
        style=discord.TextStyle.paragraph,
        required=True
    )
    pack = TextInput(
        label="Pack choisi (unitaire / pack4 / pack8)",
        placeholder="unitaire = 25€ | pack4 = 99€/mois | pack8 = 179€/mois",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        pack_choisi = self.pack.value.strip().lower()
        if "4" in pack_choisi or "pack4" in pack_choisi:
            prix = PRIX_MINI_PACK_4
            label_prix = f"{PRIX_MINI_PACK_4}€/mois (pack 4 miniatures)"
        elif "8" in pack_choisi or "pack8" in pack_choisi:
            prix = PRIX_MINI_PACK_8
            label_prix = f"{PRIX_MINI_PACK_8}€/mois (pack 8 miniatures)"
        else:
            prix = PRIX_MINIATURE_UNITAIRE
            label_prix = f"{PRIX_MINIATURE_UNITAIRE}€ (unitaire)"

        await creer_commande(
            interaction=interaction,
            type_commande="Miniature",
            nom_chaine=self.nom_chaine.value,
            description=self.description.value,
            prix=prix,
            label_prix=label_prix
        )


class ModalMontage(Modal, title="Commander un Montage Vidéo"):
    nom_chaine = TextInput(label="Nom de ta chaîne YouTube", placeholder="Ex: LeoProd", required=True)
    duree = TextInput(
        label="Durée estimée de la vidéo finale (en minutes)",
        placeholder="Ex: 10",
        required=True
    )
    description = TextInput(
        label="Description / style souhaité",
        placeholder="Ex: transitions dynamiques, sous-titres, musique fournie…",
        style=discord.TextStyle.paragraph,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            duree_min = float(self.duree.value.strip().replace(",", "."))
        except ValueError:
            await interaction.response.send_message(
                "❌ Durée invalide, entre un nombre (ex: 10).", ephemeral=True
            )
            return

        prix = round(duree_min * PRIX_MONTAGE_PAR_MINUTE, 2)
        label_prix = f"{prix}€ ({duree_min} min × {PRIX_MONTAGE_PAR_MINUTE}€)"

        await creer_commande(
            interaction=interaction,
            type_commande="Montage",
            nom_chaine=self.nom_chaine.value,
            description=self.description.value,
            prix=prix,
            label_prix=label_prix,
            duree=duree_min
        )


class BoutonsPrix(View):
    """Boutons dans le salon privé pour définir prix + délai"""
    def __init__(self, commande_id: str):
        super().__init__(timeout=None)
        self.commande_id = commande_id

    @discord.ui.button(label="💰 Définir prix & délai", style=discord.ButtonStyle.success, custom_id="btn_prix_delai")
    async def definir_prix(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != TON_ID:
            await interaction.response.send_message("❌ Réservé au créateur.", ephemeral=True)
            return
        await interaction.response.send_modal(ModalPrixDelai(self.commande_id))

    @discord.ui.button(label="✅ Marquer terminé", style=discord.ButtonStyle.primary, custom_id="btn_termine")
    async def marquer_termine(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != TON_ID:
            await interaction.response.send_message("❌ Réservé au créateur.", ephemeral=True)
            return
        await changer_statut(interaction, self.commande_id, "✅ Terminé")

    @discord.ui.button(label="❌ Annuler", style=discord.ButtonStyle.danger, custom_id="btn_annuler")
    async def annuler(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != TON_ID:
            await interaction.response.send_message("❌ Réservé au créateur.", ephemeral=True)
            return
        await changer_statut(interaction, self.commande_id, "❌ Annulé")


class ModalPrixDelai(Modal, title="Définir prix final & délai"):
    prix_final = TextInput(label="Prix final (€)", placeholder="Ex: 25", required=True)
    delai_jours = TextInput(label="Délai de livraison (jours)", placeholder="Ex: 3", required=True)

    def __init__(self, commande_id: str):
        super().__init__()
        self.commande_id = commande_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            prix = float(self.prix_final.value.strip().replace(",", "."))
            delai = int(self.delai_jours.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ Valeurs invalides.", ephemeral=True)
            return

        data = load_data()
        if self.commande_id not in data:
            await interaction.response.send_message("❌ Commande introuvable.", ephemeral=True)
            return

        commande = data[self.commande_id]
        commande["prix_final"] = prix
        commande["delai_jours"] = delai
        commande["statut"] = "⏳ En cours"
        date_livraison = datetime.now() + timedelta(days=delai)
        commande["date_livraison"] = date_livraison.strftime("%d/%m/%Y")
        save_data(data)

        await interaction.response.send_message(
            f"✅ Prix et délai enregistrés ! Mise à jour du planning…", ephemeral=True
        )

        await maj_tableau(interaction.guild, data)
        await maj_planning(interaction.guild, data)
        await envoyer_message_client(interaction.guild, commande, prix, delai, date_livraison)


# ─────────────────────────────────────────────
#  FONCTIONS PRINCIPALES
# ─────────────────────────────────────────────

async def creer_commande(interaction, type_commande, nom_chaine, description, prix, label_prix, duree=None):
    """Crée une nouvelle commande, le salon client, et met à jour le tableau."""
    guild = interaction.guild
    client = interaction.user

    # Générer un ID unique
    commande_id = f"{type_commande[:4].upper()}-{int(datetime.now().timestamp())}"

    # Créer le salon privé client
    category = guild.get_channel(CATEGORY_CLIENTS_ID)
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        client: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.get_member(TON_ID): discord.PermissionOverwrite(read_messages=True, send_messages=True),
    }
    salon_client = await guild.create_text_channel(
        name=f"commande-{nom_chaine.lower().replace(' ', '-')}",
        category=category,
        overwrites=overwrites
    )

    # Sauvegarder la commande
    data = load_data()
    data[commande_id] = {
        "id": commande_id,
        "type": type_commande,
        "client_id": client.id,
        "client_nom": str(client),
        "nom_chaine": nom_chaine,
        "description": description,
        "prix_estime": prix,
        "label_prix": label_prix,
        "duree": duree,
        "prix_final": None,
        "delai_jours": None,
        "date_livraison": None,
        "statut": "🔔 Nouvelle",
        "salon_client_id": salon_client.id,
        "date_commande": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "paiement": "⏳ En attente"
    }
    save_data(data)

    # Répondre au client
    await interaction.response.send_message(
        f"✅ Ta commande **{type_commande}** a bien été reçue ! "
        f"Retrouve les détails dans {salon_client.mention} 🎉",
        ephemeral=True
    )

    # Message de bienvenue dans le salon client
    embed_client = discord.Embed(
        title=f"📦 Commande {type_commande} — {commande_id}",
        color=discord.Color.blue()
    )
    embed_client.add_field(name="👤 Client", value=client.mention, inline=True)
    embed_client.add_field(name="📺 Chaîne", value=nom_chaine, inline=True)
    embed_client.add_field(name="💰 Tarif estimé", value=label_prix, inline=True)
    embed_client.add_field(name="📝 Description", value=description, inline=False)
    embed_client.set_footer(text="Le créateur va bientôt confirmer le prix final et le délai !")
    await salon_client.send(f"Bonjour {client.mention} ! 👋", embed=embed_client)

    # Notification dans le tableau privé
    salon_tableau = guild.get_channel(SALON_TABLEAU_ID)
    if salon_tableau:
        embed_notif = discord.Embed(
            title=f"🔔 Nouvelle commande — {commande_id}",
            color=discord.Color.orange()
        )
        embed_notif.add_field(name="Type", value=type_commande, inline=True)
        embed_notif.add_field(name="Client", value=f"{client.mention} ({nom_chaine})", inline=True)
        embed_notif.add_field(name="Prix estimé", value=label_prix, inline=True)
        embed_notif.add_field(name="Description", value=description, inline=False)
        embed_notif.add_field(name="Salon client", value=salon_client.mention, inline=True)
        await salon_tableau.send(embed=embed_notif, view=BoutonsPrix(commande_id))

    # Mise à jour du tableau complet
    await maj_tableau(guild, data)


async def maj_tableau(guild, data):
    """Met à jour (ou crée) le message tableau dans le salon privé."""
    salon = guild.get_channel(SALON_TABLEAU_ID)
    if not salon:
        return

    if not data:
        return

    lines = []
    lines.append("```")
    lines.append(f"{'ID':<18} {'Type':<12} {'Chaîne':<20} {'Prix':<12} {'Livraison':<12} {'Statut':<18} {'Paiement'}")
    lines.append("─" * 105)
    for cmd in data.values():
        prix_str = f"{cmd['prix_final']}€" if cmd["prix_final"] else f"~{cmd['prix_estime']}€"
        livraison = cmd["date_livraison"] or "À définir"
        lines.append(
            f"{cmd['id']:<18} {cmd['type']:<12} {cmd['nom_chaine'][:18]:<20} "
            f"{prix_str:<12} {livraison:<12} {cmd['statut']:<18} {cmd['paiement']}"
        )
    lines.append("```")

    tableau_text = "\n".join(lines)
    embed = discord.Embed(
        title="📋 Tableau des commandes",
        description=tableau_text,
        color=discord.Color.dark_blue(),
        timestamp=datetime.now()
    )
    embed.set_footer(text="Dernière mise à jour")

    # Chercher un message existant avec ce titre pour le modifier
    async for msg in salon.history(limit=50):
        if msg.author == guild.me and msg.embeds and "Tableau des commandes" in msg.embeds[0].title:
            await msg.edit(embed=embed)
            return

    await salon.send(embed=embed)


async def maj_planning(guild, data):
    """Met à jour le planning dans le salon dédié."""
    salon = guild.get_channel(SALON_PLANNING_ID)
    if not salon:
        return

    commandes_actives = [c for c in data.values() if c["statut"] not in ("✅ Terminé", "❌ Annulé") and c["date_livraison"]]
    commandes_actives.sort(key=lambda x: datetime.strptime(x["date_livraison"], "%d/%m/%Y"))

    embed = discord.Embed(
        title="📅 Planning de livraison",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )

    if not commandes_actives:
        embed.description = "*Aucune commande en cours pour l'instant.*"
    else:
        for cmd in commandes_actives:
            val = (
                f"👤 **Client :** {cmd['client_nom']}\n"
                f"📺 **Chaîne :** {cmd['nom_chaine']}\n"
                f"💰 **Prix :** {cmd['prix_final']}€\n"
                f"📌 **Statut :** {cmd['statut']}\n"
                f"💳 **Paiement :** {cmd['paiement']}"
            )
            embed.add_field(
                name=f"🗓️ {cmd['date_livraison']} — {cmd['type']} ({cmd['id']})",
                value=val,
                inline=False
            )

    embed.set_footer(text="Dernière mise à jour")

    async for msg in salon.history(limit=20):
        if msg.author == guild.me and msg.embeds and "Planning" in msg.embeds[0].title:
            await msg.edit(embed=embed)
            return

    await salon.send(embed=embed)


async def envoyer_message_client(guild, commande, prix, delai, date_livraison):
    """Envoie le récap prix + demande d'acompte dans le salon client."""
    salon = guild.get_channel(commande["salon_client_id"])
    if not salon:
        return

    acompte = round(prix / 2, 2)
    client = guild.get_member(commande["client_id"])

    embed = discord.Embed(
        title="💰 Confirmation de ta commande",
        color=discord.Color.gold()
    )
    embed.add_field(name="📦 Type", value=commande["type"], inline=True)
    embed.add_field(name="💵 Prix total", value=f"**{prix}€**", inline=True)
    embed.add_field(name="📅 Livraison estimée", value=date_livraison.strftime("%d/%m/%Y"), inline=True)
    embed.add_field(
        name="💳 Acompte à payer maintenant",
        value=f"**{acompte}€** (50% du total)\nLe solde de **{acompte}€** sera dû à la livraison.",
        inline=False
    )
    embed.add_field(
        name="📲 Comment payer ?",
        value=f"Envoie l'acompte via **PayPal** à `{PAYPAL_EMAIL}`\n> ⚠️ Sélectionne **\"Envoyer à un ami\"** pour éviter les frais\nUne fois le paiement effectué, confirme-le ici !",
        inline=False
    )
    embed.set_footer(text="Une fois l'acompte reçu, ta commande sera lancée ! 🚀")

    mention = client.mention if client else "Client"
    await salon.send(f"{mention} voici le récapitulatif de ta commande :", embed=embed)


async def changer_statut(interaction, commande_id, nouveau_statut):
    data = load_data()
    if commande_id not in data:
        await interaction.response.send_message("❌ Commande introuvable.", ephemeral=True)
        return
    data[commande_id]["statut"] = nouveau_statut
    save_data(data)
    await interaction.response.send_message(f"✅ Statut mis à jour : **{nouveau_statut}**", ephemeral=True)
    await maj_tableau(interaction.guild, data)
    await maj_planning(interaction.guild, data)


# ─────────────────────────────────────────────
#  COMMANDES SLASH
# ─────────────────────────────────────────────

@bot.command()
async def setup(ctx):
    """!setup — Envoie le message de commande dans #commandes (à lancer une seule fois)"""
    if ctx.author.id != TON_ID:
        return

    salon = bot.get_channel(SALON_COMMANDE_ID)
    if not salon:
        await ctx.send("❌ Salon commande introuvable. Vérifie SALON_COMMANDE_ID dans bot.py")
        return

    embed = discord.Embed(
        title="🎨  Studio Créatif — Commandez ici !",
        description=(
            "Bienvenue ! Choisis le service dont tu as besoin :\n\n"
            "**🎨 Miniature YouTube**\n"
            f"• Unitaire : **{PRIX_MINIATURE_UNITAIRE}€**\n"
            f"• Pack 4/mois : **{PRIX_MINI_PACK_4}€/mois**\n"
            f"• Pack 8/mois : **{PRIX_MINI_PACK_8}€/mois**\n\n"
            "**🎬 Montage Vidéo**\n"
            f"• **{PRIX_MONTAGE_PAR_MINUTE}€ / minute** de rendu final\n\n"
            "👇 Clique sur le bouton correspondant pour passer commande !"
        ),
        color=discord.Color.blurple()
    )
    embed.set_footer(text="Un salon privé sera créé pour suivre ta commande.")
    await salon.send(embed=embed, view=MenuCommande())
    await ctx.send("✅ Message de commande envoyé !", ephemeral=True)


@bot.command()
async def livrer(ctx, commande_id: str):
    """!livrer COMMANDE_ID — Envoie un message au client pour indiquer que c'est prêt"""
    if ctx.author.id != TON_ID:
        return
    data = load_data()
    if commande_id not in data:
        await ctx.send("❌ Commande introuvable.")
        return
    commande = data[commande_id]
    salon = bot.get_channel(commande["salon_client_id"])
    if not salon:
        await ctx.send("❌ Salon client introuvable.")
        return

    client = ctx.guild.get_member(commande["client_id"])
    mention = client.mention if client else "Client"
    acompte = round((commande["prix_final"] or commande["prix_estime"]) / 2, 2)

    embed = discord.Embed(
        title="🎉 Ta commande est prête !",
        description=(
            f"Ton **{commande['type']}** est terminé et prêt à être livré !\n\n"
            f"💳 **Solde restant à payer : {acompte}€**\n"
            f"Envoie le paiement via **PayPal** à `{PAYPAL_EMAIL}`\n"
            "> ⚠️ Sélectionne **\"Envoyer à un ami\"** pour éviter les frais\n\n"
            "Une fois le paiement confirmé, je t'enverrai le fichier final directement ici. 🎁"
        ),
        color=discord.Color.green()
    )
    await salon.send(f"{mention}", embed=embed)

    data[commande_id]["statut"] = "📬 Livraison en attente"
    save_data(data)
    await maj_tableau(ctx.guild, data)
    await maj_planning(ctx.guild, data)
    await ctx.send(f"✅ Message de livraison envoyé dans {salon.mention}")


@bot.command()
async def paiement(ctx, commande_id: str, statut: str = "reçu"):
    """!paiement COMMANDE_ID [reçu/acompte] — Marque le paiement"""
    if ctx.author.id != TON_ID:
        return
    data = load_data()
    if commande_id not in data:
        await ctx.send("❌ Commande introuvable.")
        return

    if "acompte" in statut.lower():
        data[commande_id]["paiement"] = "✅ Acompte reçu"
    else:
        data[commande_id]["paiement"] = "✅ Payé intégralement"
        data[commande_id]["statut"] = "✅ Terminé"

    save_data(data)
    await maj_tableau(ctx.guild, data)
    await maj_planning(ctx.guild, data)
    await ctx.send(f"✅ Paiement mis à jour pour {commande_id}")


# ─────────────────────────────────────────────
#  EVENTS
# ─────────────────────────────────────────────

@bot.event
async def on_ready():
    print(f"✅ Bot connecté : {bot.user} ({bot.user.id})")
    # Réenregistrer les vues persistantes au redémarrage
    bot.add_view(MenuCommande())
    print("📋 Views persistantes chargées.")


bot.run(TOKEN)

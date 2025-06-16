"""
Email templates for TrackImmo with clean, simple design matching Supabase template.
"""
from typing import Dict, Any, List
from datetime import datetime

# TrackImmo brand colors (keeping same branding)
PRIMARY_COLOR = "#6c63ff"  # Similar to Supabase gradient
SECONDARY_COLOR = "#8b84ff"  # Secondary gradient color
LOGO_URL = "https://trackimmo.app/_next/image?url=%2Fassets%2Fimages%2Fti-logo.png&w=64&q=75"

def get_base_template() -> str:
    """Base HTML template with clean, simple design matching Supabase style."""
    return """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      line-height: 1.6;
      color: #343a40;
      margin: 0;
      padding: 0;
      background-color: #f8f9fa;
    }}
    .container {{
      max-width: 600px;
      margin: 0 auto;
      padding: 20px;
      background-color: #ffffff;
      border-radius: 8px;
      box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
    }}
    .header {{
      text-align: center;
      padding-bottom: 20px;
      border-bottom: 1px solid #e9ecef;
    }}
    .logo {{
      max-width: 150px;
      height: auto;
    }}
    .content {{
      padding: 20px 0;
    }}
    .button {{
      display: inline-block;
      background: linear-gradient(45deg, #6c63ff, #8b84ff);
      color: white;
      text-decoration: none;
      padding: 12px 25px;
      border-radius: 30px;
      font-weight: 600;
      margin: 20px 0;
      text-align: center;
      box-shadow: 0 4px 15px rgba(108, 99, 255, 0.3);
    }}
    .button:hover {{
      background: linear-gradient(45deg, #5046e5, #6c63ff);
      box-shadow: 0 6px 20px rgba(108, 99, 255, 0.4);
    }}
    .footer {{
      text-align: center;
      padding-top: 20px;
      border-top: 1px solid #e9ecef;
      color: #6c757d;
      font-size: 14px;
    }}
    .footer a {{
      color: #6c63ff;
      text-decoration: none;
    }}
    h1 {{
      color: #343a40;
      font-size: 24px;
      font-weight: 600;
      margin-top: 0;
    }}
    h2 {{
      color: #6c63ff;
      font-size: 20px;
      font-weight: 600;
      margin: 25px 0 15px 0;
    }}
    p {{
      margin: 0 0 15px;
    }}
    .property-item {{
      border: 1px solid #e9ecef;
      border-radius: 5px;
      padding: 15px;
      margin-bottom: 10px;
      background-color: #f8f9fa;
    }}
    .property-header {{
      font-weight: 600;
      color: #343a40;
      margin-bottom: 5px;
    }}
    .property-price {{
      color: #6c63ff;
      font-weight: bold;
      font-size: 16px;
    }}
    .property-details {{
      color: #6c757d;
      font-size: 14px;
    }}
    .stats-box {{
      background-color: #f8f9fa;
      border: 1px solid #e9ecef;
      border-radius: 5px;
      padding: 20px;
      margin: 20px 0;
      text-align: center;
    }}
    .stat-number {{
      font-size: 24px;
      font-weight: bold;
      color: #6c63ff;
    }}
    .alert-box {{
      background-color: #f8d7da;
      border: 1px solid #f5c6cb;
      border-radius: 5px;
      padding: 15px;
      margin: 20px 0;
      color: #721c24;
    }}
    .success-box {{
      background-color: #d4edda;
      border: 1px solid #c3e6cb;
      border-radius: 5px;
      padding: 15px;
      margin: 20px 0;
      color: #155724;
    }}
    .code-block {{
      background-color: #f8f9fa;
      border: 1px solid #e9ecef;
      border-radius: 5px;
      padding: 10px;
      font-family: 'Courier New', monospace;
      font-size: 12px;
      margin: 10px 0;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <img src="{logo_url}" alt="TrackImmo" class="logo" width="150" height="50">
    </div>
    
    <div class="content">
      {content}
    </div>
    
    <div class="footer">
      <p>© 2025 TrackImmo. Tous droits réservés.</p>
      <p>Si vous avez des questions, contactez-nous à <a href="mailto:contact@trackimmo.app">contact@trackimmo.app</a></p>
    </div>
  </div>
</body>
</html>
"""

def get_client_notification_template(client: Dict[str, Any], properties: List[Dict[str, Any]]) -> str:
    """
    Generate clean HTML template for client notification.
    
    Args:
        client: Client data
        properties: List of assigned properties
        
    Returns:
        HTML email content
    """
    first_name = client.get('first_name', 'Client')
    property_count = len(properties)
    
    # Calculate basic stats
    total_value = sum(prop.get('price', 0) for prop in properties if prop.get('price'))
    avg_price = total_value // property_count if property_count > 0 else 0
    
    # Format properties list (show first 3)
    properties_html = ""
    for prop in properties[:3]:
        address = prop.get('address_raw', 'Adresse non disponible')
        city = prop.get('city_name', '')
        price = prop.get('price', 0)
        surface = prop.get('surface', 0)
        rooms = prop.get('rooms', 0)
        prop_type = prop.get('property_type', 'Autre')
        
        # Format price
        price_str = f"{price:,}€".replace(',', ' ') if price else "Prix non disponible"
        
        # Format property type in French
        type_translations = {
            'house': 'Maison',
            'apartment': 'Appartement',
            'land': 'Terrain',
            'commercial': 'Commercial',
            'other': 'Autre'
        }
        prop_type_fr = type_translations.get(prop_type, prop_type.title())
        
        # Format details
        details = [prop_type_fr]
        if surface:
            details.append(f"{surface}m²")
        if rooms:
            details.append(f"{rooms} pièces")
        
        details_str = " • ".join(details)
        
        properties_html += f"""
        <div class="property-item">
            <div class="property-header">{address}, {city}</div>
            <div class="property-price">{price_str}</div>
            <div class="property-details">{details_str}</div>
        </div>
        """
    
    # Add "and more" if there are more properties
    if property_count > 3:
        properties_html += f"""
        <div class="property-item" style="text-align: center; background-color: #e9ecef;">
            <div style="color: #6c63ff; font-weight: bold;">
                + {property_count - 3} autres propriétés disponibles dans votre tableau de bord
            </div>
        </div>
        """
    
    # Main content
    content = f"""
    <h1>Nouvelles propriétés disponibles !</h1>
    
    <p>Bonjour {first_name},</p>
    
    <p>Excellente nouvelle ! Nous avons trouvé <strong>{property_count} nouvelles propriétés</strong> qui correspondent parfaitement à vos critères de recherche.</p>
    
    <div class="success-box">
        <p style="margin: 0; font-weight: 600;">
            🎯 Ces propriétés ont été sélectionnées selon vos préférences et représentent des opportunités uniques sur votre marché.
        </p>
    </div>
    
    <div class="stats-box">
        <div class="stat-number">{property_count}</div>
        <div>Nouvelles propriétés</div>
        {f'<div style="margin-top: 15px;"><strong>Prix moyen:</strong> {avg_price:,}€'.replace(',', ' ') + '</div>' if avg_price else ''}
    </div>
    
    <h2>🏠 Aperçu de vos nouvelles opportunités</h2>
    
    {properties_html}
    
    <div style="text-align: center; margin: 30px 0;">
        <a href="https://trackimmo.app/dashboard" class="button">
            Voir toutes mes propriétés
        </a>
    </div>
    
    <p>N'hésitez pas à nous contacter si vous avez des questions. Notre équipe est là pour vous accompagner dans votre réussite !</p>
    
    <p style="margin-top: 25px;">
        Bien cordialement,<br>
        <strong>L'équipe TrackImmo</strong>
    </p>
    """
    
    # Generate full HTML
    base_template = get_base_template()
    return base_template.format(
        title=f"TrackImmo - {property_count} nouvelles propriétés",
        logo_url=LOGO_URL,
        content=content
    )

def get_error_notification_template(client_id: str, error_message: str) -> str:
    """
    Generate clean HTML template for error notification to CTO.
    
    Args:
        client_id: Client ID that failed
        error_message: Error details
        
    Returns:
        HTML email content
    """
    content = f"""
    <h1>🚨 Alerte Système TrackImmo</h1>
    
    <p>Bonjour,</p>
    
    <p>Une erreur critique s'est produite lors du traitement d'un client après 3 tentatives.</p>
    
    <div class="alert-box">
        <p style="margin: 0; font-weight: 600;">
            Échec du traitement client après 3 tentatives
        </p>
    </div>
    
    <p><strong>Client ID:</strong> {client_id}</p>
    <p><strong>Timestamp:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    
    <h2>Détails de l'erreur</h2>
    <div class="code-block">
        {error_message}
    </div>
    
    <p>Veuillez vérifier les logs et intervenir manuellement si nécessaire.</p>
    
    <div style="text-align: center; margin: 30px 0;">
        <a href="https://trackimmo.app/admin" class="button">
            Accéder au panel admin
        </a>
    </div>
    
    <p>Cordialement,<br>
    <strong>Système TrackImmo</strong></p>
    """
    
    base_template = get_base_template()
    return base_template.format(
        title="TrackImmo - Alerte Système",
        logo_url=LOGO_URL,
        content=content
    )

def get_welcome_template(client: Dict[str, Any]) -> str:
    """
    Generate welcome email template for new clients.
    
    Args:
        client: New client data
        
    Returns:
        HTML email content
    """
    first_name = client.get('first_name', 'Client')
    subscription_type = client.get('subscription_type', 'découverte')
    
    content = f"""
    <h1>Bienvenue chez TrackImmo !</h1>
    
    <p>Bonjour {first_name},</p>
    
    <p>Nous sommes ravis de vous accueillir dans la communauté TrackImmo ! 🎉</p>
    
    <div class="success-box">
        <p style="margin: 0; font-weight: 600;">
            Votre abonnement <strong>{subscription_type.title()}</strong> est maintenant actif.
        </p>
    </div>
    
    <h2>🚀 Prochaines étapes</h2>
    
    <div style="margin: 20px 0;">
        <p><strong>1.</strong> Nous analysons actuellement vos villes et critères de recherche</p>
        <p><strong>2.</strong> Vous recevrez vos premières propriétés dans les prochaines heures</p>
        <p><strong>3.</strong> Connectez-vous à votre tableau de bord pour suivre vos opportunités</p>
    </div>
    
    <div style="text-align: center; margin: 30px 0;">
        <a href="https://trackimmo.app/dashboard" class="button">
            Accéder à mon tableau de bord
        </a>
    </div>
    
    <p>Si vous avez des questions, n'hésitez pas à nous contacter. Notre équipe est là pour vous aider à maximiser vos résultats !</p>
    
    <p style="margin-top: 25px;">
        Excellente journée,<br>
        <strong>L'équipe TrackImmo</strong>
    </p>
    """
    
    base_template = get_base_template()
    return base_template.format(
        title="Bienvenue chez TrackImmo",
        logo_url=LOGO_URL,
        content=content
    )

def get_monthly_notification_template(client: Dict[str, Any]) -> str:
    """
    Generate monthly notification template to inform client about upcoming addresses.
    
    Args:
        client: Client data
        
    Returns:
        HTML email content
    """
    first_name = client.get('first_name', 'Client')
    send_day = client.get('send_day', 'bientôt')
    
    content = f"""
    <h1>Vos nouvelles propriétés arrivent !</h1>
    
    <p>Bonjour {first_name},</p>
    
    <p>C'est le moment de votre mise à jour mensuelle TrackImmo ! 🏠</p>
    
    <div class="success-box">
        <p style="margin: 0; font-weight: 600;">
            📅 Nous préparons actuellement vos nouvelles propriétés pour le {send_day} du mois.
        </p>
    </div>
    
    <h2>Ce qui vous attend</h2>
    
    <div style="margin: 20px 0;">
        <p>✨ <strong>Nouvelles opportunités:</strong> Propriétés fraîchement identifiées selon vos critères</p>
        <p>🎯 <strong>Sélection personnalisée:</strong> Adaptée à vos villes et types de biens préférés</p>
        <p>📊 <strong>Données enrichies:</strong> Informations complètes sur chaque propriété</p>
    </div>
    
    <div style="text-align: center; margin: 30px 0;">
        <a href="https://trackimmo.app/dashboard" class="button">
            Accéder à mon tableau de bord
        </a>
    </div>
    
    <p>Restez connecté pour ne rien manquer de vos prochaines opportunités immobilières !</p>
    
    <p style="margin-top: 25px;">
        À très bientôt,<br>
        <strong>L'équipe TrackImmo</strong>
    </p>
    """
    
    base_template = get_base_template()
    return base_template.format(
        title="TrackImmo - Vos nouvelles propriétés arrivent",
        logo_url=LOGO_URL,
        content=content
    )

def get_insufficient_addresses_template(client_id: str, found_count: int, requested_count: int) -> str:
    """
    Generate template to notify CTO when not enough addresses are found for a client.
    
    Args:
        client_id: Client ID
        found_count: Number of addresses found
        requested_count: Number of addresses requested
        
    Returns:
        HTML email content
    """
    content = f"""
    <h1>⚠️ Adresses insuffisantes - TrackImmo</h1>
    
    <p>Bonjour,</p>
    
    <p>Un client n'a pas reçu suffisamment d'adresses lors de son traitement.</p>
    
    <div class="alert-box">
        <p style="margin: 0; font-weight: 600;">
            Attention: Nombre d'adresses insuffisant pour le client
        </p>
    </div>
    
    <div class="stats-box">
        <p><strong>Client ID:</strong> {client_id}</p>
        <p><strong>Adresses trouvées:</strong> {found_count}</p>
        <p><strong>Adresses demandées:</strong> {requested_count}</p>
        <p><strong>Timestamp:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
    
    <h2>Actions recommandées</h2>
    
    <div style="margin: 20px 0;">
        <p>• Vérifier les critères de recherche du client</p>
        <p>• Lancer un nouveau scraping pour les villes du client</p>
        <p>• Ajuster les paramètres d'âge des propriétés si nécessaire</p>
        <p>• Contacter le client pour expliquer la situation</p>
    </div>
    
    <div style="text-align: center; margin: 30px 0;">
        <a href="https://trackimmo.app/admin/client/{client_id}" class="button">
            Voir le client dans l'admin
        </a>
    </div>
    
    <p>Cordialement,<br>
    <strong>Système TrackImmo</strong></p>
    """
    
    base_template = get_base_template()
    return base_template.format(
        title="TrackImmo - Adresses insuffisantes",
        logo_url=LOGO_URL,
        content=content
    )
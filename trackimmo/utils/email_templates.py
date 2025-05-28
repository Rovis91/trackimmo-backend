"""
Email templates for TrackImmo with HTML design.
"""
from typing import Dict, Any, List
from datetime import datetime

# TrackImmo brand colors
PRIMARY_COLOR = "#6565f1"  # Purple
SECONDARY_COLOR = "#e9489d"  # Pink
LOGO_URL = "https://trackimmo.app/_next/image?url=%2Fassets%2Fimages%2Fti-logo.png"

def get_base_template() -> str:
    """Base HTML template with TrackImmo branding."""
    return """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TrackImmo</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f8f9fa;
        }
        
        .container {
            max-width: 600px;
            margin: 0 auto;
            background-color: white;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        
        .header {
            background: linear-gradient(135deg, {primary_color} 0%, {secondary_color} 100%);
            padding: 30px 20px;
            text-align: center;
            color: white;
        }
        
        .logo {
            max-width: 120px;
            height: auto;
            margin-bottom: 15px;
        }
        
        .header h1 {
            font-size: 24px;
            font-weight: 600;
            margin: 0;
        }
        
        .content {
            padding: 40px 30px;
        }
        
        .greeting {
            font-size: 18px;
            margin-bottom: 20px;
            color: #2d3748;
        }
        
        .highlight-box {
            background: linear-gradient(135deg, {primary_color}15 0%, {secondary_color}15 100%);
            border-left: 4px solid {primary_color};
            padding: 20px;
            margin: 25px 0;
            border-radius: 8px;
        }
        
        .stats {
            display: flex;
            justify-content: space-around;
            margin: 30px 0;
            text-align: center;
        }
        
        .stat-item {
            flex: 1;
            padding: 15px;
        }
        
        .stat-number {
            font-size: 28px;
            font-weight: bold;
            color: {primary_color};
            display: block;
        }
        
        .stat-label {
            font-size: 14px;
            color: #666;
            margin-top: 5px;
        }
        
        .properties-list {
            margin: 25px 0;
        }
        
        .property-item {
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 15px;
            background-color: #fafafa;
        }
        
        .property-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 10px;
        }
        
        .property-address {
            font-weight: 600;
            color: #2d3748;
            font-size: 16px;
        }
        
        .property-price {
            font-weight: bold;
            color: {secondary_color};
            font-size: 16px;
        }
        
        .property-details {
            font-size: 14px;
            color: #666;
            margin-top: 8px;
        }
        
        .property-type {
            display: inline-block;
            background-color: {primary_color};
            color: white;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 12px;
            margin-right: 8px;
        }
        
        .cta-button {
            display: inline-block;
            background: linear-gradient(135deg, {primary_color} 0%, {secondary_color} 100%);
            color: white;
            padding: 15px 30px;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 600;
            margin: 20px 0;
            text-align: center;
            transition: transform 0.2s;
        }
        
        .cta-button:hover {
            transform: translateY(-1px);
        }
        
        .footer {
            background-color: #f7fafc;
            padding: 25px 30px;
            text-align: center;
            border-top: 1px solid #e2e8f0;
            font-size: 14px;
            color: #666;
        }
        
        .footer a {
            color: {primary_color};
            text-decoration: none;
        }
        
        .divider {
            height: 1px;
            background: linear-gradient(90deg, transparent 0%, {primary_color} 50%, transparent 100%);
            margin: 30px 0;
        }
        
        @media (max-width: 600px) {
            .container {
                margin: 0;
                border-radius: 0;
            }
            
            .content {
                padding: 30px 20px;
            }
            
            .stats {
                flex-direction: column;
            }
            
            .stat-item {
                margin-bottom: 15px;
            }
            
            .property-header {
                flex-direction: column;
                align-items: flex-start;
            }
            
            .property-price {
                margin-top: 5px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <img src="{logo_url}" alt="TrackImmo" class="logo">
            <h1>{header_title}</h1>
        </div>
        
        <div class="content">
            {content}
        </div>
        
        <div class="footer">
            <p>Vous recevez cet email car vous êtes abonné aux notifications TrackImmo.</p>
            <p>
                <a href="https://trackimmo.app">Accéder au tableau de bord</a> | 
                <a href="https://trackimmo.app/contact">Nous contacter</a>
            </p>
            <p style="margin-top: 15px; font-size: 12px; color: #999;">
                © 2024 TrackImmo. Tous droits réservés.
            </p>
        </div>
    </div>
</body>
</html>
"""

def get_client_notification_template(client: Dict[str, Any], properties: List[Dict[str, Any]]) -> str:
    """
    Generate HTML template for client notification.
    
    Args:
        client: Client data
        properties: List of assigned properties
        
    Returns:
        HTML email content
    """
    first_name = client.get('first_name', 'Client')
    property_count = len(properties)
    
    # Calculate stats
    total_value = sum(prop.get('price', 0) for prop in properties if prop.get('price'))
    avg_price = total_value // property_count if property_count > 0 else 0
    
    property_types = {}
    for prop in properties:
        prop_type = prop.get('property_type', 'Autre')
        property_types[prop_type] = property_types.get(prop_type, 0) + 1
    
    # Format properties list
    properties_html = ""
    for prop in properties[:5]:  # Show max 5 properties
        address = prop.get('address_raw', 'Adresse non disponible')
        city = prop.get('city_name', '')
        price = prop.get('price', 0)
        surface = prop.get('surface', 0)
        rooms = prop.get('rooms', 0)
        prop_type = prop.get('property_type', 'Autre')
        sale_date = prop.get('sale_date', '')
        
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
        prop_type_fr = type_translations.get(prop_type, prop_type)
        
        # Format details
        details = []
        if surface:
            details.append(f"{surface}m²")
        if rooms:
            details.append(f"{rooms} pièces")
        if sale_date:
            details.append(f"Vendu le {sale_date}")
        
        details_str = " • ".join(details)
        
        properties_html += f"""
        <div class="property-item">
            <div class="property-header">
                <div class="property-address">{address}, {city}</div>
                <div class="property-price">{price_str}</div>
            </div>
            <div class="property-details">
                <span class="property-type">{prop_type_fr}</span>
                {details_str}
            </div>
        </div>
        """
    
    # Add "and more" if there are more properties
    if property_count > 5:
        properties_html += f"""
        <div class="property-item" style="text-align: center; background-color: {PRIMARY_COLOR}10; border-color: {PRIMARY_COLOR};">
            <div style="color: {PRIMARY_COLOR}; font-weight: bold;">
                + {property_count - 5} autres propriétés disponibles dans votre tableau de bord
            </div>
        </div>
        """
    
    # Main content
    content = f"""
    <div class="greeting">
        Bonjour {first_name},
    </div>
    
    <p>Excellente nouvelle ! Nous avons trouvé <strong>{property_count} nouvelles propriétés</strong> qui correspondent parfaitement à vos critères de recherche.</p>
    
    <div class="highlight-box">
        <p style="margin: 0; font-weight: 600; color: {PRIMARY_COLOR};">
            🎯 Ces propriétés ont été sélectionnées selon vos préférences et représentent des opportunités uniques sur votre marché.
        </p>
    </div>
    
    <div class="stats">
        <div class="stat-item">
            <span class="stat-number">{property_count}</span>
            <div class="stat-label">Nouvelles propriétés</div>
        </div>
        <div class="stat-item">
            <span class="stat-number">{f"{avg_price:,}€".replace(',', ' ') if avg_price else "N/A"}</span>
            <div class="stat-label">Prix moyen</div>
        </div>
        <div class="stat-item">
            <span class="stat-number">{len(property_types)}</span>
            <div class="stat-label">Types de biens</div>
        </div>
    </div>
    
    <div class="divider"></div>
    
    <h3 style="color: {PRIMARY_COLOR}; margin-bottom: 20px;">🏠 Aperçu de vos nouvelles opportunités</h3>
    
    <div class="properties-list">
        {properties_html}
    </div>
    
    <div style="text-align: center; margin: 30px 0;">
        <a href="https://trackimmo.app/dashboard" class="cta-button">
            Voir toutes mes propriétés
        </a>
    </div>
    
    <p>N'hésitez pas à nous contacter si vous avez des questions. Notre équipe est là pour vous accompagner dans votre réussite !</p>
    
    <p style="margin-top: 25px;">
        Cordialement,<br>
        <strong>L'équipe TrackImmo</strong>
    </p>
    """
    
    # Generate full HTML
    base_template = get_base_template()
    return base_template.format(
        primary_color=PRIMARY_COLOR,
        secondary_color=SECONDARY_COLOR,
        logo_url=LOGO_URL,
        header_title=f"{property_count} nouvelles propriétés vous attendent !",
        content=content
    )

def get_error_notification_template(client_id: str, error_message: str) -> str:
    """
    Generate HTML template for error notification to admin.
    
    Args:
        client_id: Client ID that failed
        error_message: Error details
        
    Returns:
        HTML email content
    """
    content = f"""
    <div class="greeting">
        Alerte Système TrackImmo
    </div>
    
    <div class="highlight-box" style="border-left-color: #e53e3e; background-color: #fed7d7;">
        <p style="margin: 0; font-weight: 600; color: #e53e3e;">
            🚨 Échec du traitement client après 3 tentatives
        </p>
    </div>
    
    <p><strong>Client ID:</strong> {client_id}</p>
    <p><strong>Timestamp:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    
    <div style="background-color: #f7fafc; padding: 15px; border-radius: 8px; margin: 20px 0;">
        <p><strong>Détails de l'erreur:</strong></p>
        <code style="background-color: #e2e8f0; padding: 10px; border-radius: 4px; display: block; margin-top: 10px; font-family: monospace;">
            {error_message}
        </code>
    </div>
    
    <p>Veuillez vérifier les logs et intervenir manuellement si nécessaire.</p>
    
    <div style="text-align: center; margin: 30px 0;">
        <a href="https://trackimmo.app/admin" class="cta-button">
            Accéder au panel admin
        </a>
    </div>
    """
    
    base_template = get_base_template()
    return base_template.format(
        primary_color=PRIMARY_COLOR,
        secondary_color=SECONDARY_COLOR,
        logo_url=LOGO_URL,
        header_title="Alerte Système",
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
    <div class="greeting">
        Bienvenue {first_name} !
    </div>
    
    <p>Nous sommes ravis de vous accueillir dans la communauté TrackImmo ! 🎉</p>
    
    <div class="highlight-box">
        <p style="margin: 0; font-weight: 600;">
            Votre abonnement <strong>{subscription_type.title()}</strong> est maintenant actif.
        </p>
    </div>
    
    <h3 style="color: {PRIMARY_COLOR}; margin: 25px 0 15px 0;">🚀 Prochaines étapes</h3>
    
    <div style="margin: 20px 0;">
        <div style="display: flex; align-items: center; margin-bottom: 15px;">
            <div style="width: 30px; height: 30px; background-color: {PRIMARY_COLOR}; color: white; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-right: 15px; font-weight: bold;">1</div>
            <div>Nous analysons actuellement vos villes et critères de recherche</div>
        </div>
        <div style="display: flex; align-items: center; margin-bottom: 15px;">
            <div style="width: 30px; height: 30px; background-color: {PRIMARY_COLOR}; color: white; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-right: 15px; font-weight: bold;">2</div>
            <div>Vous recevrez vos premières propriétés dans les prochaines heures</div>
        </div>
        <div style="display: flex; align-items: center; margin-bottom: 15px;">
            <div style="width: 30px; height: 30px; background-color: {PRIMARY_COLOR}; color: white; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-right: 15px; font-weight: bold;">3</div>
            <div>Connectez-vous à votre tableau de bord pour suivre vos opportunités</div>
        </div>
    </div>
    
    <div style="text-align: center; margin: 30px 0;">
        <a href="https://trackimmo.app/dashboard" class="cta-button">
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
        primary_color=PRIMARY_COLOR,
        secondary_color=SECONDARY_COLOR,
        logo_url=LOGO_URL,
        header_title="Bienvenue chez TrackImmo !",
        content=content
    )
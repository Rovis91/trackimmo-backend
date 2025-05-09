# Documentation du scraping ImmoData

Ce document détaille les sélecteurs HTML et techniques utilisés pour extraire les données immobilières du site ImmoData.

## Structure HTML cible

ImmoData présente les propriétés immobilières sous forme de liste avec une structure HTML spécifique. Chaque propriété est contenue dans un élément distinct avec des classes CSS identifiables.

## Sélecteurs HTML

### Conteneurs principaux

```yaml
property_container:
  selector: 'div.md:h-full.flex.flex-col.md:w-112.w-full.order-1.md:order-2'
  description: "Conteneur principal qui englobe toutes les propriétés"

property_item:
  selector: 'div.border-b.border-b-gray-100'
  description: "Élément individuel représentant une propriété"

property_content:
  selector: 'div.text-sm.relative.font-sans'
  description: "Contenu détaillé de la propriété à extraire"

address:
  selector: 'p.text-gray-700.font-bold.truncate'
  format: "{adresse} - {ville}"
  description: "Adresse complète et ville, séparés par un tiret"
  exemple: "123 Rue de Paris - Lille"
  extraction: |
    match = re.search(r'(.+) - (.+)', text)
    if match:
        address = match.group(1).strip()
        city = match.group(2).strip()

price:
  selector: 'p.text-primary-500.font-bold.whitespace-nowrap span'
  format: "Valeur numérique (suppression des espaces et caractères non numériques)"
  description: "Prix de vente de la propriété"
  exemple: "450 000 €"
  extraction: |
    price = int(re.sub(r'[^0-9]', '', text))

rooms:
  selector: 'svg.fa-objects-column + span.font-semibold'
  format: "Valeur numérique"
  description: "Nombre de pièces du bien"
  exemple: "4"
  extraction: |
    rooms = int(text.strip()) if text.strip().isdigit() else None

surface:
  selector: 'svg.fa-ruler-combined + span.font-semibold'
  format: "Valeur numérique suivie de m²"
  description: "Surface en mètres carrés"
  exemple: "85 m²"
  extraction: |
    surface = float(text.replace('m²', '').strip().replace(',', '.'))

date:
  selector: 'time'
  attribute: 'datetime'
  format: "Timestamp Unix en millisecondes"
  description: "Date de la transaction"
  exemple: "1654041600000"
  extraction: |
    timestamp = int(element['datetime']) // 1000
    date = datetime.fromtimestamp(timestamp).strftime('%d/%m/%Y')

details_url:
  selector: 'a.whitespace-nowrap.border.bg-primary-500'
  attribute: 'href'
  format: "URL relative à préfixer avec 'https://www.immo-data.fr'"
  description: "Lien vers la page de détails"
  exemple: "/analyse/00abc123"
  extraction: |
    url = f"https://www.immo-data.fr{element['href']}" if element['href'].startswith('/') else element['href']
```

## Technique de scraping

1.Génération d'URLs: Créer des URLs paramétrées par ville, code postal, dates et types de biens
2.Navigation avec Playwright: Utiliser Playwright pour charger les pages et attendre le chargement complet
3.Extraction du HTML: Récupérer le contenu HTML de la page
4.Parsing avec BeautifulSoup: Analyser le HTML et extraire les données selon les sélecteurs
5.Stockage intermédiaire: Sauvegarder les données brutes dans un CSV intermédiaire

## Format de sortie

Les données extraites sont sauvegardées dans un CSV avec la structure suivante:

``` csv
url,count,property
https://www.immo-data.fr/explorateur/transaction/recherche?center=3.057;50.629&zoom=12.5&propertytypes=1&minmonthyear=Janvier%202024,1,"<div class='text-sm relative font-sans'>...</div>"
```

Chaque ligne contient:

* L'URL source
* Un compteur de position
* Le HTML brut de la propriété (à analyser ultérieurement)

## Exemple d'implémentation

``` python
async def extract_data(self, content: str) -> Optional[List[Dict[str, Any]]]:
    """
    Extract property data from page content.
    """
    if not content:
        return None
    
    try:
        soup = BeautifulSoup(content, 'html.parser')
        
        container = soup.find('div', class_=selectors.CONTAINER_CLASS)
        if not container:
            return None

        properties = container.find_all(
            'div', 
            class_=selectors.PROPERTY_CLASS,
            limit=100
        )
        
        if not properties:
            return None

        extracted_properties = []
        for index, prop in enumerate(properties, start=1):
            content_div = prop.find('div', class_=selectors.PROPERTY_CONTENT_CLASS)
            if content_div:
                extracted_properties.append({
                    'url': self.url,
                    'count': index,
                    'property': str(content_div)
                })
        
        return extracted_properties
    
    except Exception as e:
        logger.error(f"Failed to extract data: {str(e)}")
        return None
```

## Gestion des erreurs

* Page non chargée: Si la page ne se charge pas correctement, attendre et réessayer jusqu'à 3 fois
* Structure HTML modifiée: Vérifier périodiquement les sélecteurs et les adapter si nécessaire
* Anti-scraping: Respecter un délai entre les requêtes (minimum 1 seconde) et utiliser un user-agent réaliste

## Notes importantes

1. ImmoData est susceptible de modifier sa structure HTML sans préavis
2. Le site peut implémenter des mesures anti-scraping qui nécessiteraient des adaptations
3. Les performances peuvent varier selon le nombre de propriétés à extraire

# Algorithme d'estimation des prix immobiliers

Ce document décrit l'algorithme utilisé pour estimer les prix actuels des biens immobiliers à partir des données historiques.

## Vue d'ensemble

L'algorithme combine plusieurs facteurs pour estimer le prix actuel d'un bien:

1. Prix historique du bien
2. Évolution des prix dans la zone géographique
3. Caractéristiques spécifiques du bien
4. Données de référence de prix au m²

## Entrées de l'algorithme

- **Propriété**: Adresse, type, surface, prix initial, date de vente
- **Référence**: Prix au m² actuels par ville/code postal/type de bien
- **Historique**: Données sur l'évolution des prix dans la zone

## Structure détaillée

### 1. Calcul du prix de référence actuel

Le prix de référence est obtenu depuis la base de données ou via le scraping de MeilleursAgents.

```python
def get_reference_price(city, zipcode, property_type):
    # Check database first
    reference = db.query(ReferencePrice).filter_by(
        city_id=city_id, 
        property_type=property_type
    ).first()
    
    if reference:
        return reference.price_per_m2
    
    # If not available, fetch from external source
    return fetch_reference_price(city, zipcode, property_type)
```

### 2. Calcul de l'évolution des prix

Pour chaque année entre la date de vente et aujourd'hui, nous calculons un taux d'évolution:

``` python
def calculate_growth_rates(properties, city, zipcode, property_type):
    # Group properties by year
    yearly_data = {}
    for prop in properties:
        year = prop.sale_date.year
        if year not in yearly_data:
            yearly_data[year] = []
        yearly_data[year].append(prop.price_per_m2)
    
    # Calculate average price per m² for each year
    yearly_averages = {year: sum(prices)/len(prices) for year, prices in yearly_data.items()}
    
    # Calculate year-over-year growth rates
    growth_rates = {}
    years = sorted(yearly_averages.keys())
    for i in range(len(years)-1):
        current_year = years[i]
        next_year = years[i+1]
        growth_rate = (yearly_averages[next_year] / yearly_averages[current_year]) - 1
        growth_rates[current_year] = max(min(growth_rate, 0.30), -0.30)  # Cap at ±30%
    
    return growth_rates
```

### 3. Application de l'évolution au prix historique

Le prix historique est ajusté en appliquant les taux d'évolution année par année:

``` python
def estimate_current_price(initial_price, initial_price_m2, surface, sale_year, growth_rates, current_year):
    # Start with initial price per m²
    current_price_m2 = initial_price_m2
    
    # Apply growth rates year by year
    for year in range(sale_year, current_year):
        if year in growth_rates:
            current_price_m2 *= (1 + growth_rates[year])
        else:
            # Use fallback growth rate if data missing
            current_price_m2 *= 1.03  # Default 3% annual growth
    
    # Calculate final price
    estimated_price = current_price_m2 * surface
    
    return {
        'estimated_price': estimated_price,
        'price_per_m2': current_price_m2,
        'total_growth': (current_price_m2 / initial_price_m2) - 1
    }
```

### 4. Ajustement selon les caractéristiques spécifiques

Divers facteurs peuvent influencer l'estimation:

``` python
def adjust_price(base_estimation, property_data):
    adjustments = 0
    
    # DPE adjustment
    dpe_factors = {'A': 0.05, 'B': 0.03, 'C': 0.01, 'D': 0, 'E': -0.02, 'F': -0.05, 'G': -0.08}
    if property_data.get('dpe_energy_class') in dpe_factors:
        adjustments += dpe_factors[property_data['dpe_energy_class']]
    
    # Other factors
    if property_data.get('has_elevator', False) and property_data.get('floor', 0) > 2:
        adjustments += 0.02
    
    if property_data.get('has_balcony', False) or property_data.get('has_terrace', False):
        adjustments += 0.03
    
    # Apply combined adjustment
    adjusted_price = base_estimation['estimated_price'] * (1 + adjustments)
    
    return adjusted_price
```

### 5. Calcul du score de confiance

Un score de confiance est attribué à chaque estimation:

``` python
def calculate_confidence(property_data, estimation_data, reference_data):
    score = 70  # Base score
    
    # Data age penalty
    years_since_sale = current_year - property_data['sale_year']
    age_penalty = min(years_since_sale * 5, 40)
    score -= age_penalty
    
    # Data richness bonus
    if reference_data and 'sample_size' in reference_data:
        sample_bonus = min(reference_data['sample_size'] * 2, 15)
        score += sample_bonus
    
    # Quality factor
    if property_data.get('surface') and property_data.get('rooms'):
        score += 5
    
    if property_data.get('dpe_energy_class'):
        score += 5
    
    # Price difference penalty
    if estimation_data.get('price_per_m2') and reference_data.get('price_per_m2'):
        diff_percent = abs(estimation_data['price_per_m2'] - reference_data['price_per_m2']) / reference_data['price_per_m2']
        if diff_percent > 0.3:  # More than 30% difference
            score -= 15
    
    return max(min(score, 100), 0)  # Ensure score is between 0-100
```

## Résultats

L'algorithme produit plusieurs valeurs:

- estimated_price: Estimation du prix actuel du bien
- price_per_m2: Prix estimé au m²
- total_growth_rate: Taux d'évolution depuis la date d'achat
- confidence_score: Score de confiance (0-100)

## Limitations

Dépendance aux données historiques (moins fiable dans les zones avec peu de transactions)
Ne prend pas en compte les rénovations ou dégradations spécifiques du bien
Sensibilité aux valeurs extrêmes (d'où l'importance du plafonnement des taux d'évolution)
Approximation des cycles immobiliers (simplification de la saisonnalité)

## Maintenance

L'algorithme nécessite une mise à jour régulière des prix de référence (au moins trimestrielle) pour maintenir sa pertinence.

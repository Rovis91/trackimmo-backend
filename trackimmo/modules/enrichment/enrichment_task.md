# Tâches d'implémentation du module d'enrichissement

Ce document détaille les tâches à accomplir pour développer le module d'enrichissement des données immobilières, structuré selon une approche "une étape = un fichier".

## Phase 1: Normalisation des données (01_data_normalizer.py)

- [ ] **1.1. Créer la classe de base `ProcessorBase`**
  - [ ] 1.1.1. Implémenter les méthodes communes (load_csv, save_csv)
  - [ ] 1.1.2. Définir l'interface commune pour tous les processeurs

- [ ] **1.2. Implémenter la classe `DataNormalizer`**
  - [ ] 1.2.1. Ajouter la vérification des données requises (adresse, ville, prix, date)
  - [ ] 1.2.2. Convertir les types de données appropriés (price→int, surface→int, rooms→int)
  - [ ] 1.2.3. Standardiser les formats de date (DD/MM/YYYY → YYYY-MM-DD)
  - [ ] 1.2.4. Normaliser les adresses et noms de villes (majuscules, sans accents)
  - [ ] 1.2.5. Mapper les types de propriétés français vers enum DB (Maison→house, Appartement→apartment)

- [ ] **1.3. Ajouter les validations**
  - [ ] 1.3.1. Valider la structure des adresses (détecter les formats incorrects)
  - [ ] 1.3.2. Vérifier la cohérence des dates (rejeter les dates invalides)
  - [ ] 1.3.3. Implémenter les règles de nettoyage des valeurs numériques

- [ ] **1.4. Mettre en place le système de journalisation**
  - [ ] 1.4.1. Configurer le logging détaillé du processus
  - [ ] 1.4.2. Ajouter le comptage des problèmes détectés

## Phase 2: Résolution des villes et codes postaux (02_city_resolver.py)

- [ ] **2.1. Créer la classe `CityResolver`**
  - [ ] 2.1.1. Implémenter la connexion à la base de données
  - [ ] 2.1.2. Ajouter la méthode de recherche exacte des villes
  - [ ] 2.1.3. Implémenter la méthode de recherche approximative

- [ ] **2.2. Gérer les villes nouvelles**
  - [ ] 2.2.1. Implémenter la récupération des codes postaux via l'API de géocodage
  - [ ] 2.2.2. Développer une approche statistique pour déterminer le code postal le plus fréquent
  - [ ] 2.2.3. Ajouter la création des nouvelles entrées de villes en base

- [ ] **2.3. Optimiser le traitement des villes**
  - [ ] 2.3.1. Regrouper les propriétés par nom de ville
  - [ ] 2.3.2. Implémenter un cache pour éviter les requêtes répétées
  - [ ] 2.3.3. Valider les codes INSEE et départements

## Phase 3: Géocodage des adresses (03_geocoding_service.py)

- [ ] **3.1. Implémenter la classe `GeocodingService`**
  - [ ] 3.1.1. Créer l'interface avec l'API Base Adresse Nationale
  - [ ] 3.1.2. Optimiser l'envoi de lots CSV directement à l'API
  - [ ] 3.1.3. Ajouter la logique de retry en cas d'erreur (3 essais max)

- [ ] **3.2. Filtrer les résultats**
  - [ ] 3.2.1. Implémenter la validation des scores de géocodage (minimum 0.5)
  - [ ] 3.2.2. Développer le filtrage géographique (dans la zone de scraping)
  - [ ] 3.2.3. Configurer le filtrage par code postal accepté

- [ ] **3.3. Optimiser le traitement**
  - [ ] 3.3.1. Implémenter le chunking optimal des données (5000 adresses max par requête)
  - [ ] 3.3.2. Ajouter la détection des régions aberrantes
  - [ ] 3.3.3. Gérer les cas spéciaux (adresses incomplètes)

## Phase 4: Enrichissement DPE (04_dpe_enrichment.py)

- [ ] **4.1. Implémenter la classe `DPEEnrichmentService`**
  - [ ] 4.1.1. Configurer l'accès aux fichiers DPE locaux
  - [ ] 4.1.2. Implémenter l'interface avec l'API ADEME (logements existants)
  - [ ] 4.1.3. Ajouter l'accès à l'API pour logements neufs

- [ ] **4.2. Développer la stratégie de matching**
  - [ ] 4.2.1. Implémenter le matching exact par adresse normalisée
  - [ ] 4.2.2. Ajouter le matching par numéro + rue
  - [ ] 4.2.3. Développer le matching phonétique avec Soundex
  - [ ] 4.2.4. Créer le cache des résultats DPE par code INSEE

- [ ] **4.3. Optimiser le traitement DPE**
  - [ ] 4.3.1. Implémenter le regroupement par code INSEE
  - [ ] 4.3.2. Ajouter la logique différenciée pour bâtiments neufs (post-2021)
  - [ ] 4.3.3. Configurer le système de retry avec backoff exponentiel

## Phase 5: Estimation des prix (05_price_estimator.py)

- [ ] **5.1. Implémenter la classe `PriceEstimationService`**
  - [ ] 5.1.1. Développer le calcul d'évolution temporelle des prix
  - [ ] 5.1.2. Ajouter les ajustements par type de bien et localisation
  - [ ] 5.1.3. Implémenter l'ajustement basé sur les données DPE

- [ ] **5.2. Configurer les règles d'estimation**
  - [ ] 5.2.1. Implémenter le cas des ventes récentes (< 6 mois → prix identique)
  - [ ] 5.2.2. Développer les facteurs correctifs par caractéristique
  - [ ] 5.2.3. Ajouter les plafonds d'évolution annuelle (±10%)

- [ ] **5.3. Ajouter les calculs de confiance**
  - [ ] 5.3.1. Implémenter le score de confiance basé sur l'âge de la vente
  - [ ] 5.3.2. Ajouter les facteurs DPE dans le score de confiance
  - [ ] 5.3.3. Configurer le score basé sur la qualité du géocodage

## Phase 6: Intégration DB (06_db_integrator.py)

- [ ] **6.1. Implémenter la classe `DBIntegrationService`**
  - [ ] 6.1.1. Configurer la connexion à PostgreSQL
  - [ ] 6.1.2. Développer les méthodes d'insertion dans la table addresses
  - [ ] 6.1.3. Ajouter l'insertion dans la table dpe

- [ ] **6.2. Optimiser les transactions**
  - [ ] 6.2.1. Implémenter le traitement par lots pour les insertions
  - [ ] 6.2.2. Ajouter la gestion des erreurs SQL
  - [ ] 6.2.3. Développer le logging détaillé des insertions

- [ ] **6.3. Finaliser l'intégration**
  - [ ] 6.3.1. Créer le rapport final d'intégration
  - [ ] 6.3.2. Implémenter les statistiques de réussite
  - [ ] 6.3.3. Configurer le nettoyage des fichiers temporaires

## Phase 7: Orchestration (enrichment_orchestrator.py)

- [ ] **7.1. Créer la classe `EnrichmentOrchestrator`**
  - [ ] 7.1.1. Implémenter le chargement de la configuration
  - [ ] 7.1.2. Ajouter l'initialisation de tous les services
  - [ ] 7.1.3. Développer la méthode d'exécution complète

- [ ] **7.2. Configurer le mode debug**
  - [ ] 7.2.1. Implémenter la sauvegarde des CSV intermédiaires
  - [ ] 7.2.2. Ajouter le mode de reprise (commencer à une étape spécifique)
  - [ ] 7.2.3. Développer la visualisation de progression

- [ ] **7.3. Finaliser l'interface**
  - [ ] 7.3.1. Créer l'interface CLI simple
  - [ ] 7.3.2. Ajouter les options de configuration
  - [ ] 7.3.3. Implémenter le rapport final de traitement
  
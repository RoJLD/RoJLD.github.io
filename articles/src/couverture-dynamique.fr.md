---
tldr: la couverture dynamique en delta-hedging fonctionne bien en théorie, mais les coûts de transaction, la volatilité stochastique et les contraintes de rebalancement la rendent bien plus complexe en pratique. Voici ce que j'ai appris pendant mon PFE avec EY.
---

## Introduction

Dans le cadre de mon projet de fin d'études à l'ECE Paris, réalisé en collaboration avec EY, j'ai travaillé sur la **modélisation et le pilotage de stratégies de couverture dynamique** appliquées aux portefeuilles d'assurance et bancaires.

L'objectif : comparer les modèles théoriques de hedging (Black-Scholes, modèles à volatilité locale) avec les contraintes opérationnelles réelles : coûts de transaction, fréquence de rebalancement, et gestion du basis risk.

## Le cadre théorique

Le delta-hedging repose sur une idée simple : à chaque instant, on ajuste la quantité d'actif sous-jacent détenue pour neutraliser la sensibilité du portefeuille aux mouvements de prix.

::formula
Δ = ∂V/∂S = N(d₁)   où   d₁ = [ln(S/K) + (r + σ²/2)T] / (σ√T)
::

En théorie, avec un rebalancement continu et sans coûts de transaction, le P&L de la stratégie de couverture converge vers zéro. En pratique, c'est une autre histoire.

### Hypothèses clés du modèle

- **Volatilité constante** (rarement le cas en réalité)
- **Rebalancement continu** (impossible en pratique)
- **Pas de coûts de transaction** (significatifs sur les marchés réels)
- **Liquidité parfaite** (pas toujours disponible)

## Résultats expérimentaux

Nous avons simulé plusieurs stratégies de rebalancement (quotidien, hebdomadaire, basé sur un seuil de delta) sur des données historiques et synthétiques. Voici les principales observations :

### 1. L'impact de la fréquence de rebalancement

Un rebalancement quotidien réduit l'erreur de hedging d'environ **60%** par rapport à un rebalancement hebdomadaire, mais augmente les coûts de transaction de **400%**. Le sweet spot dépend fortement du profil de volatilité et du spread bid-ask.

### 2. Volatilité stochastique vs implicite

Utiliser la volatilité implicite pour calculer le delta plutôt que la volatilité historique réduit significativement le tracking error. Cependant, dans les périodes de stress de marché, aucune approche ne performe bien, d'où l'intérêt des modèles à volatilité stochastique (Heston, SABR).

### 3. Approche par seuil de delta

Le rebalancement « intelligent » (basé sur un seuil de variation du delta plutôt qu'une fréquence fixe) offre le meilleur compromis coût/efficacité. Nous avons trouvé qu'un seuil de **Δ ± 0.05** était optimal dans nos simulations.

```
# Exemple simplifié de rebalancement par seuil
def should_rebalance(current_delta, target_delta, threshold=0.05):
    return abs(current_delta - target_delta) > threshold

# Boucle de hedging
for t in range(1, T):
    new_delta = bs_delta(S[t], K, sigma, T-t, r)
    if should_rebalance(portfolio_delta, new_delta):
        trade_quantity = new_delta - portfolio_delta
        execute_trade(trade_quantity)
        portfolio_delta = new_delta
        transaction_costs += abs(trade_quantity) * spread
```

## Leçons tirées

> Le modèle parfait n'existe pas : le vrai skill d'un quant, c'est de comprendre où et comment son modèle va casser.

Ce projet m'a appris que le passage de la théorie à la pratique en finance quantitative ne se résume pas à implémenter une formule. Il faut comprendre les contraintes opérationnelles, les coûts cachés, et surtout être capable de quantifier l'incertitude de ses propres modèles.

Si ce sujet vous intéresse, n'hésitez pas à me contacter, je suis toujours partant pour en discuter !

import json
import logging
from typing import List, Dict, Any, Union
from django.db.models import Prefetch, Q
from django.utils import timezone
from django.db.models import Case, When, Value, FloatField
from fuzzywuzzy import process, fuzz
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain.chat_models import init_chat_model
from asgiref.sync import sync_to_async
from dotenv import load_dotenv
import asyncio
import os

from .models import ProductSearchKB, ProductComboSearchKB, Product, Category, ProductCombo, ProductSection

load_dotenv()
api_key = os.getenv('LLM_API_KEY')
provider = os.getenv('MODEL_PROVIDER')
llm_model = os.getenv('LLM_MODEL')
logger = logging.getLogger(__name__)

class SpiceSearchEngine:
    def __init__(self, model: str = None):
        # Fallbacks to ensure it doesn't crash if env vars are missing
        self.provider = provider or "perplexity"
        self.model_name = model or llm_model or "sonar"
        
        # Initialize Langchain Chat Model using unified interface
        # Openrouter uses "openai" as the provider standard for Langchain initialization
        if self.provider.lower() == 'openrouter':
            from langchain_openai import ChatOpenAI
            self.llm = ChatOpenAI(
                model=self.model_name,
                openai_api_key=api_key,
                openai_api_base="https://openrouter.ai/api/v1",
                temperature=0.1
            )
        else:
            self.llm = init_chat_model(
                self.model_name, 
                model_provider=self.provider, 
                temperature=0.1, 
                api_key=api_key
            )
            
        self._product_cache = {}
    
    def generate_synonyms(self, name: str, context: str = "", is_combo: bool = False) -> List[str]:
        """LLM generates 20+ India-wide spice search terms with REGIONAL VARIANTS"""
        context_type = "spice combo" if is_combo else "individual spice"
        
        regional_prompt = ChatPromptTemplate.from_template("""
        Generate 25+ e-commerce search terms Indians use for {context_type}: "{name}"
        Context: {context}

        REQUIRED: Include ALL regional Indian names, Hindi/English mixes, misspellings, 
        weights (50g/100g/250g/500g), forms (powder/whole/raw), packs.

        EXAMPLES:
        TURMERIC/HALDI: ["haldi", "haldee", "haldi powder", "turmeric", "turmeric powder", 
                        "haldipowder", "manjal", "pasupu", "halud", "haldhar", "arishina", 
                        "haladi", "haridra", "haldi 100g", "turmeric 250g", "organic haldi"]
        CHILLI/MIRCH: ["mirch", "chilli", "chili", "lal mirch", "green chilli", "mirchi powder", 
                      "vip mirch", "red chilli", "hari mirch", "mirch powder 100g"]

        COMMON PATTERNS: "{name} powder", "{name} 100g", "organic {name}", "{name} pack"

        Return ONLY valid JSON: {{"synonyms": ["term1", "term2", ...]}} NO EXPLANATIONS
        """)
        
        try:
            chain = regional_prompt | self.llm | JsonOutputParser()
            result = chain.invoke({"name": name, "context": context, "context_type": context_type})
            synonyms = result.get("synonyms", [])
            
            # Spice-specific boosts
            common_boosts = {
                'haldi': ['haldi', 'haldee', 'haldhi', 'haldi powder', 'turmeric powder', 'manjal', 'pasupu'],
                'turmeric': ['haldi', 'haldee', 'turmeric powder', 'haldi powder', 'haldi 100g'],
                'mirch': ['mirch', 'chilli', 'chili', 'lal mirch', 'mirchi', 'vip mirch', 'red chilli'],
                'chilli': ['mirch', 'chilli powder', 'green chilli', 'lal mirch', 'vip mirch']
            }
            
            name_lower = name.lower()
            for base, variants in common_boosts.items():
                if base in name_lower:
                    synonyms = list(set(variants + synonyms))
                    break
            
            unique_synonyms = list(dict.fromkeys([s.strip().lower() for s in synonyms if s.strip()]))
            return unique_synonyms[:25]
        except Exception as e:
            logger.error(f"Synonym generation failed: {e}")
            fallback = [name.lower(), f"{name} powder".lower(), f"{name} 100g".lower()]
            
            spice_fallbacks = {
                'haldi': ['haldi', 'haldee', 'turmeric', 'manjal', 'pasupu'],
                'turmeric': ['haldi', 'haldee', 'turmeric powder', 'haldi powder'],
                'mirch': ['mirch', 'chilli', 'chili', 'lal mirch', 'vip mirch'],
                'chilli': ['mirch', 'chilli powder', 'green chilli', 'lal mirch', 'vip mirch']
            }
            
            for key, variants in spice_fallbacks.items():
                if key in name_lower:
                    fallback.extend(variants)
                    break
            return list(dict.fromkeys(fallback))[:15]
    
    def ensure_search_kb(self, product_or_combo: Union[Product, ProductCombo]) -> None:
        """Ensure search KB exists and is fresh (7 days)"""
        if isinstance(product_or_combo, Product):
            kb_model, kb_field = ProductSearchKB, 'product'
            context = f"{product_or_combo.category.name} {product_or_combo.spice_form}"
            is_combo = False
        elif isinstance(product_or_combo, ProductCombo):
            kb_model, kb_field = ProductComboSearchKB, 'combo'
            product_names = [p.name for p in product_or_combo.products.all()[:3]]
            context = f"Combo: {', '.join(product_names)}"
            is_combo = True
        else:
            logger.error(f"Invalid type: {type(product_or_combo)}")
            return
        
        kb, created = kb_model.objects.get_or_create(**{kb_field: product_or_combo})
        days_old = (timezone.now() - kb.last_updated).days
        
        if created or days_old > 7:
            synonyms = self.generate_synonyms(product_or_combo.name, context, is_combo=is_combo)
            kb.synonyms = synonyms
            kb.save()
            logger.info(f"{'Created' if created else f'Refreshed ({days_old}d)'} KB for {product_or_combo.name}")

    async def a_generate_synonyms(self, name: str, context: str = "", is_combo: bool = False) -> List[str]:
        """Asynchronous version of generate_synonyms"""
        context_type = "spice combo" if is_combo else "individual spice"
        
        regional_prompt = ChatPromptTemplate.from_template("""
        Generate 25+ e-commerce search terms Indians use for {context_type}: "{name}"
        Context: {context}

        REQUIRED: Include ALL regional Indian names, Hindi/English mixes, misspellings, 
        weights (50g/100g/250g/500g), forms (powder/whole/raw), packs.

        EXAMPLES:
        TURMERIC/HALDI: ["haldi", "haldee", "haldi powder", "turmeric", "turmeric powder", 
                        "haldipowder", "manjal", "pasupu", "halud", "haldhar", "arishina", 
                        "haladi", "haridra", "haldi 100g", "turmeric 250g", "organic haldi"]
        CHILLI/MIRCH: ["mirch", "chilli", "chili", "lal mirch", "green chilli", "mirchi powder", 
                      "vip mirch", "red chilli", "hari mirch", "mirch powder 100g"]

        COMMON PATTERNS: "{name} powder", "{name} 100g", "organic {name}", "{name} pack"

        Return ONLY valid JSON: {{"synonyms": ["term1", "term2", ...]}} NO EXPLANATIONS
        """)
        
        try:
            chain = regional_prompt | self.llm | JsonOutputParser()
            result = await chain.ainvoke({"name": name, "context": context, "context_type": context_type})
            synonyms = result.get("synonyms", [])
            
            common_boosts = {
                'haldi': ['haldi', 'haldee', 'haldhi', 'haldi powder', 'turmeric powder', 'manjal', 'pasupu'],
                'turmeric': ['haldi', 'haldee', 'turmeric powder', 'haldi powder', 'haldi 100g'],
                'mirch': ['mirch', 'chilli', 'chili', 'lal mirch', 'mirchi', 'vip mirch', 'red chilli'],
                'chilli': ['mirch', 'chilli powder', 'green chilli', 'lal mirch', 'vip mirch']
            }
            
            name_lower = name.lower()
            for base, variants in common_boosts.items():
                if base in name_lower:
                    synonyms = list(set(variants + synonyms))
                    break
            
            unique_synonyms = list(dict.fromkeys([s.strip().lower() for s in synonyms if s.strip()]))
            return unique_synonyms[:25]
        except Exception as e:
            logger.error(f"Async synonym generation failed: {e}")
            fallback = [name.lower(), f"{name} powder".lower(), f"{name} 100g".lower()]
            
            spice_fallbacks = {
                'haldi': ['haldi', 'haldee', 'turmeric', 'manjal', 'pasupu'],
                'turmeric': ['haldi', 'haldee', 'turmeric powder', 'haldi powder'],
                'mirch': ['mirch', 'chilli', 'chili', 'lal mirch', 'vip mirch'],
                'chilli': ['mirch', 'chilli powder', 'green chilli', 'lal mirch', 'vip mirch']
            }
            
            for key, variants in spice_fallbacks.items():
                if key in name_lower:
                    fallback.extend(variants)
                    break
            return list(dict.fromkeys(fallback))[:15]

    @sync_to_async
    def _get_or_create_kb(self, kb_model, kwargs):
        return kb_model.objects.get_or_create(**kwargs)

    @sync_to_async
    def _save_kb(self, kb):
        kb.save()

    async def a_ensure_search_kb(self, product_or_combo: Union[Product, ProductCombo]) -> None:
        """Asynchronous version of ensure_search_kb"""
        if isinstance(product_or_combo, Product):
            kb_model, kb_field = ProductSearchKB, 'product'
            context = f"{product_or_combo.category.name} {product_or_combo.spice_form}"
            is_combo = False
        elif isinstance(product_or_combo, ProductCombo):
            kb_model, kb_field = ProductComboSearchKB, 'combo'
            
            @sync_to_async
            def get_product_names():
                return [p.name for p in product_or_combo.products.all()[:3]]
            product_names = await get_product_names()
            
            context = f"Combo: {', '.join(product_names)}"
            is_combo = True
        else:
            logger.error(f"Invalid type: {type(product_or_combo)}")
            return
        
        kb, created = await self._get_or_create_kb(kb_model, {kb_field: product_or_combo})
        days_old = (timezone.now() - kb.last_updated).days
        
        if created or days_old > 7:
            synonyms = await self.a_generate_synonyms(product_or_combo.name, context, is_combo=is_combo)
            kb.synonyms = synonyms
            await self._save_kb(kb)
            logger.info(f"{'Created' if created else f'Refreshed ({days_old}d)'} Async KB for {product_or_combo.name}")

    
    def unified_search(self, query: str, top_k: int = 20, score_threshold: int = 70) -> Dict[str, Any]:
        """SINGLE ENDPOINT: Unified search + recommendations ranked by score"""
        query = query.strip().lower()
        
        # 1. Direct fuzzy search (highest priority)
        direct_results = self._fuzzy_search_all(query, top_k // 2, score_threshold)
        
        # 2. Fast fallback recommendations
        other_recs = self._other_recommendations(query, top_k // 2)
        
        all_results = direct_results + other_recs
        scored_results = self._rank_and_dedupe(all_results, top_k)
        
        products = [r for r in scored_results if r['type'] == 'product']
        combos = [r for r in scored_results if r['type'] == 'combo']
        
        return {
            'query': query,
            'total_results': len(scored_results),
            'products': products,
            'combos': combos,
            'stats': {
                'direct_matches': len(direct_results),
                'other_recs': len(other_recs)
            }
        }
    
    def _fuzzy_search_all(self, query: str, top_k: int, threshold: int) -> List[Dict]:
        """SPEEDUP: <100ms with filtering + exact match boost"""
        results = []
        
        # SPEEDUP #1: Filter active products FIRST ([:200] limit)
        product_kbs = ProductSearchKB.objects.select_related('product__category').filter(
            product__is_active=True, 
            product__stock__gt=0
        )[:200]
        
        # SPEEDUP #2: Build synonyms in memory (no DB hits)
        all_synonyms = []
        for kb in product_kbs:
            synonyms = kb.get_synonyms_list()
            product = kb.product
            all_synonyms.extend([(syn, product.id, product.name, 'product') for syn in synonyms])
            all_synonyms.append((product.name.lower(), product.id, product.name, 'product'))
        
        # FIXED #3: token_set_ratio + EXACT MATCH BOOST (chilli → VIP Mirch #1)
        if all_synonyms:
            matches = process.extract(
                query, [item[0] for item in all_synonyms],
                scorer=fuzz.token_set_ratio,  # Better for "chilli" vs "vip mirch"
                limit=min(top_k * 4, 100)
            )
            
            scored = {}
            for match, score in matches:
                if score >= threshold:
                    _, pid, pname, ptype = next(item for item in all_synonyms if item[0] == match)
                    
                    # CRITICAL: Exact/partial match boosts
                    exact_boost = 30 if fuzz.ratio(query, match) > 95 else 0
                    partial_boost = 15 if fuzz.partial_ratio(query, match) > 90 else 0
                    scored[pid] = max(scored.get(pid, 0), score + exact_boost + partial_boost)
            
            # SPEEDUP #4: Batch fetch top candidates
            top_ids = sorted(scored.items(), key=lambda x: x[1], reverse=True)[:top_k]
            if top_ids:
                products = Product.objects.filter(
                    id__in=[pid for pid, _ in top_ids],
                    is_active=True, stock__gt=0
                ).select_related('category')
                results.extend(self._format_products(products, scored))
        
        # Combos with same optimizations
        results.extend(self._fuzzy_search_combos_fast(query, top_k//2, threshold))
        return results[:top_k]
    
    def _format_products(self, products, scored_scores: Dict) -> List[Dict]:
        """Batch formatting for speed"""
        return [{
            'id': p.id, 'name': p.name, 'slug': p.slug, 'type': 'product',
            'category': p.category.name, 'spice_form': p.spice_form,
            'price': float(p.final_price), 'original_price': float(p.price),
            'discount': p.discount_percentage, 'weight': p.weight, 'unit': p.unit,
            'image': p.image.url if p.image else None,
            'score': scored_scores.get(p.id, 0), 'score_type': 'direct',
            'in_stock': p.stock, 'is_featured': p.is_featured
        } for p in products]
    
    def _fuzzy_search_combos_fast(self, query: str, top_k: int, threshold: int) -> List[Dict]:
        """Optimized combo search"""
        results = []
        combo_kbs = ProductComboSearchKB.objects.select_related('combo').filter(
            combo__is_active=True
        )[:100]
        
        all_synonyms = []
        for kb in combo_kbs:
            synonyms = kb.get_synonyms_list()
            combo = kb.combo
            all_synonyms.extend([(syn, combo.id, combo.name, 'combo') for syn in synonyms])
            all_synonyms.append((combo.name.lower(), combo.id, combo.name, 'combo'))
        
        if not all_synonyms:
            return []
        
        matches = process.extract(
            query, [item[0] for item in all_synonyms],
            scorer=fuzz.token_set_ratio,
            limit=top_k * 2
        )
        
        scored_combos = {}
        for match, score in matches:
            if score >= threshold:
                _, cid, cname, _ = next(item for item in all_synonyms if item[0] == match)
                exact_boost = 30 if fuzz.ratio(query, match) > 95 else 0
                scored_combos[cid] = max(scored_combos.get(cid, 0), score + exact_boost)
        
        top_ids = [cid for cid, _ in sorted(scored_combos.items(), key=lambda x: x[1], reverse=True)[:top_k]]
        combos = ProductCombo.objects.filter(
            id__in=top_ids, is_active=True
        ).prefetch_related('products')
        
        for c in combos:
            results.append({
                'id': c.id, 'name': c.display_title or c.name, 'slug': c.slug, 'type': 'combo',
                'price': float(c.final_price), 'original_price': float(c.price),
                'discount': c.discount_percentage, 'products_count': c.products.count(),
                'image': c.image.url if c.image else None,
                'score': scored_combos.get(c.id, 0), 'score_type': 'direct',
                'products': [p.name for p in c.products.all()[:3]]
            })
        return results
    
    def _other_recommendations(self, query: str, top_k: int) -> List[Dict]:
        """Fast category + trending fallback"""
        results = []
        
        # Category match
        category_match = Category.objects.filter(name__icontains=query).first()
        if category_match:
            products = Product.objects.filter(
                category=category_match, is_active=True, stock__gt=0
            ).select_related('category')[:top_k//4]
            results.extend(self._format_products(products, {p.id: 75 for p in products}))
        
        # Trending/featured
        trending_products = Product.objects.filter(
            is_featured=True, is_active=True, stock__gt=0
        ).select_related('category')[:top_k//4]
        results.extend(self._format_products(trending_products, {p.id: 60 for p in trending_products}))
        
        return results[:top_k//2]
    
    def _rank_and_dedupe(self, results: List[Dict], top_k: int) -> List[Dict]:
        """Rank by score, dedupe by ID"""
        scored = {}
        score_weights = {'direct': 1.0, 'category': 0.8, 'trending': 0.5}
        
        for item in results:
            item_id = (item['type'], item['id'])
            if item_id not in scored or item['score'] > scored[item_id]['score']:
                scored[item_id] = {**item, 'score': item['score'] * score_weights.get(item['score_type'], 0.5)}
        
        return sorted(scored.values(), key=lambda x: x['score'], reverse=True)[:top_k]
    
    # Compatibility methods (unchanged from original)
    def _category_recommendations(self, query: str, top_k: int) -> List[Dict]:
        return self._other_recommendations(query, top_k)
    
    def _semantic_recommendations(self, query: str, top_k: int) -> List[Dict]:
        return []
    
    def _trending_recommendations(self, top_k: int) -> List[Dict]:
        return []
    
    def _product_base_dict(self, product):
        return {
            'name': product.name,
            'slug': product.slug,
            'type': 'product',
            'category': product.category.name,
            'spice_form': product.spice_form,
            'weight': product.weight,
            'unit': product.unit,
            'organic': getattr(product, 'organic', False),
            'in_stock': product.stock,
            'is_featured': product.is_featured,
            'discount': getattr(product, 'discount_percentage', 0)
        }

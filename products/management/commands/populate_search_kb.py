# shop/management/commands/populate_search_kb.py
from django.core.management.base import BaseCommand
from products.recommendations import SpiceSearchEngine
from products.models import Product, ProductCombo

class Command(BaseCommand):
    help = 'Populate LLM search KB for products and combos'
    
    def add_arguments(self, parser):
        # Optional: add flags like --force to regenerate everything
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force regenerate even fresh entries',
        )
    
    def handle(self, *args, **options):
        engine = SpiceSearchEngine()
        force = options.get('force', False)
        
        products = Product.objects.filter(is_active=True)
        combos = ProductCombo.objects.filter(is_active=True)
        
        self.stdout.write(f'Processing {products.count()} products...')
        for i, product in enumerate(products, 1):
            engine.ensure_search_kb(product)
            self.stdout.write(f'  [{i}/{products.count()}] ✓ {product.name}')
        
        self.stdout.write(f'\nProcessing {combos.count()} combos...')
        for i, combo in enumerate(combos, 1):
            engine.ensure_search_kb(combo)
            self.stdout.write(f'  [{i}/{combos.count()}] ✓ {combo.name}')
        
        self.stdout.write(self.style.SUCCESS('\n✅ Done! Search KB is ready.'))

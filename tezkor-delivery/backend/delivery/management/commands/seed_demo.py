from decimal import Decimal
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from delivery.models import Category, Order, OrderEvent, OrderItem, Product, User


class Command(BaseCommand):
    help = "Namuna menyu va faqat lokal sinov uchun demo hisoblarni yaratadi."

    def add_arguments(self, parser):
        parser.add_argument("--menu-only", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG and not options["menu_only"]:
            raise CommandError("seed_demo faqat DJANGO_DEBUG=true muhitida ishlaydi.")
        categories = {}
        for position, (name, icon) in enumerate([("Burgerlar", "burger"), ("Pitsalar", "pizza"), ("Gazaklar", "snack"), ("Salatlar", "salad"), ("Ichimliklar", "drink")]):
            categories[name], _ = Category.objects.get_or_create(name=name, defaults={"icon": icon, "position": position})
        menu = [
            ("Klassik burger", "Burgerlar", 35000, "Sersuv mol go‘shti, cheddar pishlog‘i, yangi sabzavotlar va maxsus sous.", "photo-1568901346375-23c9450c58cd", "Bestseller", "280 g"),
            ("Double cheeseburger", "Burgerlar", 49000, "Ikki qavat go‘sht, ikki karra cheddar va betakror ta’m.", "photo-1550547660-d9450f859349", "Tavsiya", "380 g"),
            ("Pepperoni pitsa", "Pitsalar", 69000, "Pepperoni, cho‘ziluvchan mozzarella va pomidor sousi.", "photo-1628840042765-356cda07504e", "Bestseller", "30 sm"),
            ("Margarita pitsa", "Pitsalar", 59000, "Yangi rayhon, mozzarella pishlog‘i va pishgan pomidorlar.", "photo-1574071318508-1cdbab80d002", "", "30 sm"),
            ("Qarsildoq fri", "Gazaklar", 18000, "Oltinrang qovurilgan kartoshka, yengil tuz va sevimli sousingiz.", "photo-1573080496219-bb080dd4f877", "", "150 g"),
            ("Sezar salat", "Salatlar", 39000, "Tovuq filesi, salat barglari, parmesan va Sezar sousi.", "photo-1512621776951-a57141f2eefd", "Yengil tanlov", "250 g"),
            ("Tovuq burger", "Burgerlar", 32000, "Qarsildoq tovuq filesi, yangi salat va mayin sarimsoqli sous.", "photo-1606755962773-d324e0a13086", "", "260 g"),
            ("Limonli limonad", "Ichimliklar", 15000, "Tabiiy limon, yalpiz, muz va ajoyib tetiklik.", "photo-1513558161293-cdaf765edfd7", "Tetiklantiradi", "400 ml"),
            ("Muzli qahva", "Ichimliklar", 22000, "Yangi espresso, mayin sut va muz — kuningizga quvvat.", "photo-1461023058943-07fcbe16d735", "", "350 ml"),
        ]
        products = []
        local_images = ["classic-burger.jpg", "double-burger.jpg", "pepperoni.jpg", "margarita.jpg", "fries.jpg", "salad.jpg", "chicken-burger.jpg", "lemonade.svg", "iced-coffee.jpg"]
        for name, category, price, description, image, badge, weight in menu:
            local_image = "/menu/" + local_images[len(products)]
            product, created = Product.objects.get_or_create(name=name, defaults={"category": categories[category], "price": price, "description": description, "image_url": local_image, "badge": badge, "weight": weight})
            if not created and product.image_url == f"https://images.unsplash.com/{image}?w=700&auto=format&fit=crop&q=80":
                product.image_url = local_image
                product.save(update_fields=["image_url"])
            products.append(product)
        if options["menu_only"]:
            self.stdout.write(self.style.SUCCESS("Restoran menyusi tayyor. Demo hisoblar va buyurtmalar yaratilmadi."))
            return
        demo_users = {}
        for role, name in [("customer", "Aziz Karimov"), ("courier", "Sardor Aliyev"), ("admin", "Madina Rahimova")]:
            user, created = User.objects.get_or_create(username=f"demo_{role}", defaults={"role": role, "first_name": name.split()[0], "last_name": name.split()[1]})
            if created:
                user.set_unusable_password()
                user.save(update_fields=["password"])
            demo_users[role] = user
        for role in ["customer", "courier"]:
            user, created = User.objects.get_or_create(username=f"sample_{role}", defaults={"role": role, "first_name": "Sinov", "last_name": "mijoz" if role == "customer" else "kuryer"})
            if created:
                user.set_unusable_password()
                user.save(update_fields=["password"])
        if not Order.objects.filter(customer=demo_users["customer"]).exists():
            examples = [([0, 4], "pending", "Yunusobod tumani, Amir Temur ko‘chasi 12, 24-xonadon"), ([2, 7], "ready", "Chilonzor tumani, Bunyodkor ko‘chasi 8, 15-xonadon"), ([1, 4], "delivered", "Mirzo Ulug‘bek tumani, Buyuk Ipak Yo‘li 34")]
            sequence = ["pending", "confirmed", "preparing", "ready", "delivering", "delivered"]
            for indices, final_status, address in examples:
                subtotal = sum((products[index].price for index in indices), Decimal(0))
                order = Order.objects.create(customer=demo_users["customer"], courier=demo_users["courier"] if final_status != "pending" else None, status=final_status, address=address, phone="+998901234567", subtotal=subtotal, delivery_fee=settings.DELIVERY_FEE, total=subtotal + settings.DELIVERY_FEE, note="Namuna buyurtma")
                for index in indices:
                    product = products[index]
                    OrderItem.objects.create(order=order, product=product, product_name=product.name, unit_price=product.price, quantity=1)
                for order_status in sequence[:sequence.index(final_status) + 1]:
                    OrderEvent.objects.create(order=order, status=order_status, actor=demo_users["customer"] if order_status == "pending" else demo_users["admin"])
        self.stdout.write(self.style.SUCCESS("Namuna menyu, 3 demo kirish hisobi, 2 sinov hisobi va buyurtmalar tayyor."))

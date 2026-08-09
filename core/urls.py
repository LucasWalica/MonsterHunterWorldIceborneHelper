from django.urls import path

from core.views import calculator, crafting, monsters, sets, weapons
from core.views.home import home, ping

app_name = "core"

urlpatterns = [
    path("", home, name="home"),
    path("ping/", ping, name="ping"),
    path("weapons/", weapons.weapon_list, name="weapon_list"),
    path("weapons/<int:pk>/", crafting.weapon_detail, name="weapon_detail"),
    path("monsters/", monsters.monster_list, name="monster_list"),
    path("monsters/<int:pk>/", monsters.monster_detail, name="monster_detail"),
    path("calculator/", calculator.efr_calculator, name="efr_calculator"),
    path("calculator/weapons/search/", calculator.weapon_search, name="weapon_search"),
    path("sets/", sets.set_builder, name="set_builder"),
    path("sets/decorations/search/", sets.decoration_search, name="decoration_search"),
    path("sets/charms/search/", sets.charm_search, name="charm_search"),
    path("sets/optimize/", sets.optimize, name="set_optimizer"),
    path("items/<int:pk>/", crafting.item_detail, name="item_detail"),
    path("armor/<int:pk>/", crafting.armor_detail, name="armor_detail"),
]

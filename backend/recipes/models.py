from colorfield.fields import ColorField
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import models

User = get_user_model()
DEFAULT_COLOR = '#00FF00'


class Tag(models.Model):
    name = models.CharField(
        'Имя',
        max_length=100,
        unique=True
    )
    color = ColorField(
        verbose_name='Цветовой HEX-код',
        default=DEFAULT_COLOR,
        format='hex',
        unique=True
    )
    slug = models.SlugField(
        'Ссылка',
        max_length=100,
        unique=True
    )

    class Meta:
        verbose_name = 'Тэг'
        verbose_name_plural = 'Тэги'
        ordering = ['-id']

    def __str__(self):
        return self.name


class Ingredient(models.Model):
    name = models.CharField(
        'Название ингредиента',
        max_length=100
    )
    measurement_unit = models.CharField(
        'Единица измерения ингредиента',
        max_length=100
    )

    class Meta:
        verbose_name = 'Ингредиент'
        verbose_name_plural = 'Ингредиенты'
        ordering = ['name']

    def __str__(self):
        return f'{self.name}, {self.measurement_unit}.'


class Recipe(models.Model):
    author = models.ForeignKey(
        User,
        verbose_name='Автор рецепта',
        on_delete=models.CASCADE,
        related_name='recipes',
    )
    name = models.CharField(
        verbose_name='Название рецепта',
        max_length=255
    )
    image = models.ImageField(
        verbose_name='Изображение готового блюда',
        blank=True,
        null=True,
        upload_to='image_recipes/',
    )
    text = models.TextField(
        verbose_name='Описание',
    )
    ingredients = models.ManyToManyField(
        Ingredient,
        through='IngredientAmount',
        verbose_name='Ингредиенты',
    )
    tags = models.ManyToManyField(
        Tag,
        verbose_name='Теги',
        related_name='recipes',
    )
    cooking_time = models.PositiveSmallIntegerField(
        verbose_name='Время приготовления',
        validators=[
            MinValueValidator(1, 'Минимальное время приготовления - 1 минута.')
        ]
    )
    pud_date = models.DateTimeField(
        verbose_name='Дата публикации',
        auto_now_add=True
    )

    class Meta:
        verbose_name = 'Рецепт'
        verbose_name_plural = 'Рецепты'
        ordering = ['-pud_date']

    def __str__(self):
        return self.name


class IngredientAmount(models.Model):
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.CASCADE,
        related_name='recipe_ingredient',
        verbose_name='Ингредиент',
    )
    recipe = models.ForeignKey(
        Recipe,
        related_name='recipe_ingredient',
        on_delete=models.CASCADE,
        verbose_name='Рецепт',
    )
    amount = models.PositiveIntegerField(verbose_name='Количество')

    class Meta:
        verbose_name = 'Ингредиент рецепта'
        verbose_name_plural = 'Ингредиенты рецепта'
        constraints = (
            models.UniqueConstraint(fields=['ingredient', 'recipe'],
                                    name='unique_ingredients_recipe'),
        )


class FavoriteRecipe(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='favorites',
        verbose_name='Пользователь',
    )
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name='favorites',
        verbose_name='Рецепт',
    )

    class Meta:
        verbose_name = 'Избранный рецепт'
        verbose_name_plural = 'Избранные рецепты'
        ordering = ['-id']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'recipe'],
                name='unique_user_recipe'
            )
        ]


class ShoppingCart(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='list',
        verbose_name='Пользователь',
    )
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name='list',
        verbose_name='Рецепт',
    )

    class Meta:
        verbose_name = 'Корзина'
        verbose_name_plural = 'Корзины'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'recipe'],
                name='unique_user_list'
            )
        ]

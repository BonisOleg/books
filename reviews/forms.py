from django import forms
from .models import Review


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ('author_name', 'rating', 'text')
        widgets = {
            'author_name': forms.TextInput(attrs={
                'class': 'form-input', 'placeholder': 'Ваше ім\'я',
            }),
            'rating': forms.Select(attrs={'class': 'form-select'}),
            'text': forms.Textarea(attrs={
                'class': 'form-textarea', 'rows': 4,
                'placeholder': 'Ваш відгук про товар...',
            }),
        }

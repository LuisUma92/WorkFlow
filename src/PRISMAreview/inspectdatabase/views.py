from django.shortcuts import render, get_object_or_404, redirect
from django.apps import apps
from prismadb.ppORM import init_structure
from .forms import ModelSelectionForm


def select_model_view(request):
    init_structure()
    if request.method == 'POST':
        form = ModelSelectionForm(request.POST)
        if form.is_valid():
            model_name = form.cleaned_data['model_name']
            pk = form.cleaned_data['pk']
            return redirect('display_model_row', model_name=model_name, pk=pk)
    else:
        form = ModelSelectionForm()

    return render(request, 'inspectdatabase/select_model.html', {'form': form})


def display_model_row(request, model_name, pk):
    model = apps.get_model(app_label='prismadb', model_name=model_name)
    instance = get_object_or_404(model, pk=pk)

    # Convert instance to dictionary
    data = {}
    error_message = None
    for field in model._meta.fields:
        data[field.name] = getattr(instance, field.name)

    if request.method == 'POST':
        for key in data.keys():
            if key in request.POST:
                data[key] = request.POST[key]

        try:
            # use ppORM to update

            return redirect('select_model')
        except ValueError as e:
            error_message = e

    return render(
            request,
            'inspectdatabase/display_content.html',
            {'data': data, 'error': error_message}
            )

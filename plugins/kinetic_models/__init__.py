"""
Kinetic Model Plugins for IVT Kinetics Analyzer.

Sprint 9: Plugin Architecture Enhancement (PRD Section 0.12)

This package contains custom kinetic model implementations that extend
the base models provided by the application.

To create a new kinetic model plugin:

1. Create a new Python file in this directory (e.g., my_model.py)
2. Import the base class and decorator:

   from app.analysis.kinetic_models import KineticModel, kinetic_model, ModelParameters

3. Define your model class with the @kinetic_model decorator:

   @kinetic_model
   class MyCustomModel(KineticModel):
       @property
       def name(self) -> str:
           return "my_custom_model"

       # ... implement required abstract methods

4. The model will be automatically discovered and registered when the
   application loads plugins via ModelRegistry.discover_plugins()

See example_biexponential.py for a complete example implementation.
"""

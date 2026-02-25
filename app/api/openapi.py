"""
OpenAPI Documentation for IVT Kinetics Analyzer API.

Phase G.3: REST API Documentation with OpenAPI 3.0 specification.

Provides:
- OpenAPI 3.0 specification in JSON format
- Swagger UI at /api/docs
- ReDoc UI at /api/redoc
"""
from flask import Blueprint, jsonify, render_template_string

openapi_bp = Blueprint('openapi', __name__, url_prefix='/api')


OPENAPI_SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "IVT Kinetics Analyzer API",
        "description": """
REST API for the IVT Kinetics Analyzer - a scientific web application for
analyzing in-vitro transcription kinetics using Bayesian and frequentist methods.

## Authentication
This is a single-tenant application. User identification is provided via the
`X-Username` header for audit logging purposes.

## Response Format
All endpoints return JSON. Successful responses include the requested data.
Error responses include an `error` field with a description.

## Rate Limiting
No rate limiting is enforced in development. Production deployments should
configure appropriate limits via reverse proxy.
        """,
        "version": "1.0.0",
        "contact": {
            "name": "IVT Kinetics Analyzer",
        },
        "license": {
            "name": "MIT",
        }
    },
    "servers": [
        {
            "url": "/",
            "description": "Current server"
        }
    ],
    "tags": [
        {"name": "Projects", "description": "Project management endpoints"},
        {"name": "Constructs", "description": "Construct registry endpoints"},
        {"name": "Layouts", "description": "Plate layout management"},
        {"name": "Tasks", "description": "Background task monitoring"},
        {"name": "Analysis", "description": "Analysis results and versions"},
        {"name": "Calculator", "description": "Scientific calculators"},
        {"name": "Smart Planner", "description": "Experiment planning"},
        {"name": "Cross-Project", "description": "Cross-project comparisons"},
    ],
    "paths": {
        # ============ Projects ============
        "/api/projects/": {
            "get": {
                "tags": ["Projects"],
                "summary": "List all projects",
                "description": "Retrieve a list of all projects with optional filtering.",
                "parameters": [
                    {
                        "name": "include_archived",
                        "in": "query",
                        "schema": {"type": "boolean", "default": False},
                        "description": "Include archived projects"
                    },
                    {
                        "name": "draft_only",
                        "in": "query",
                        "schema": {"type": "boolean", "default": False},
                        "description": "Only return draft projects"
                    },
                    {
                        "name": "search",
                        "in": "query",
                        "schema": {"type": "string"},
                        "description": "Search term for name/description"
                    },
                    {
                        "name": "limit",
                        "in": "query",
                        "schema": {"type": "integer"},
                        "description": "Maximum number to return"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "List of projects",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "projects": {
                                            "type": "array",
                                            "items": {"$ref": "#/components/schemas/ProjectSummary"}
                                        },
                                        "count": {"type": "integer"}
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "post": {
                "tags": ["Projects"],
                "summary": "Create a new project",
                "description": "Create a new project with the specified configuration.",
                "parameters": [
                    {
                        "name": "X-Username",
                        "in": "header",
                        "schema": {"type": "string"},
                        "description": "User creating the project"
                    }
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ProjectCreate"}
                        }
                    }
                },
                "responses": {
                    "201": {
                        "description": "Project created",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Project"}
                            }
                        }
                    },
                    "400": {"$ref": "#/components/responses/BadRequest"}
                }
            }
        },
        "/api/projects/{project_id}": {
            "get": {
                "tags": ["Projects"],
                "summary": "Get project details",
                "parameters": [
                    {"$ref": "#/components/parameters/ProjectId"}
                ],
                "responses": {
                    "200": {
                        "description": "Project details",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Project"}
                            }
                        }
                    },
                    "404": {"$ref": "#/components/responses/NotFound"}
                }
            },
            "put": {
                "tags": ["Projects"],
                "summary": "Update project",
                "parameters": [
                    {"$ref": "#/components/parameters/ProjectId"},
                    {
                        "name": "X-Username",
                        "in": "header",
                        "schema": {"type": "string"}
                    }
                ],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ProjectUpdate"}
                        }
                    }
                },
                "responses": {
                    "200": {"description": "Project updated"},
                    "404": {"$ref": "#/components/responses/NotFound"}
                }
            },
            "delete": {
                "tags": ["Projects"],
                "summary": "Soft-delete project",
                "description": "Archives the project (soft delete). Can be restored later.",
                "parameters": [
                    {"$ref": "#/components/parameters/ProjectId"},
                    {
                        "name": "X-Username",
                        "in": "header",
                        "schema": {"type": "string"}
                    }
                ],
                "responses": {
                    "200": {"description": "Project archived"},
                    "404": {"$ref": "#/components/responses/NotFound"}
                }
            }
        },
        "/api/projects/{project_id}/publish": {
            "post": {
                "tags": ["Projects"],
                "summary": "Publish project",
                "description": "Move project from draft to published state.",
                "parameters": [
                    {"$ref": "#/components/parameters/ProjectId"},
                    {
                        "name": "X-Username",
                        "in": "header",
                        "schema": {"type": "string"}
                    }
                ],
                "responses": {
                    "200": {"description": "Project published"},
                    "400": {"description": "Project already published"},
                    "404": {"$ref": "#/components/responses/NotFound"}
                }
            }
        },
        "/api/projects/{project_id}/restore": {
            "post": {
                "tags": ["Projects"],
                "summary": "Restore archived project",
                "parameters": [
                    {"$ref": "#/components/parameters/ProjectId"},
                    {
                        "name": "X-Username",
                        "in": "header",
                        "schema": {"type": "string"}
                    }
                ],
                "responses": {
                    "200": {"description": "Project restored"},
                    "404": {"$ref": "#/components/responses/NotFound"}
                }
            }
        },
        # ============ Analysis ============
        "/api/projects/{project_id}/analysis": {
            "get": {
                "tags": ["Analysis"],
                "summary": "Get analysis results",
                "description": "Retrieve comprehensive analysis results including posterior summaries, fold changes, and convergence diagnostics.",
                "parameters": [
                    {"$ref": "#/components/parameters/ProjectId"},
                    {
                        "name": "version_id",
                        "in": "query",
                        "schema": {"type": "integer"},
                        "description": "Specific analysis version ID (defaults to latest)"
                    },
                    {
                        "name": "include_posterior",
                        "in": "query",
                        "schema": {"type": "boolean", "default": True},
                        "description": "Include posterior parameter summaries"
                    },
                    {
                        "name": "include_fold_changes",
                        "in": "query",
                        "schema": {"type": "boolean", "default": True},
                        "description": "Include fold change results"
                    },
                    {
                        "name": "include_convergence",
                        "in": "query",
                        "schema": {"type": "boolean", "default": True},
                        "description": "Include MCMC convergence diagnostics"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Analysis results",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/AnalysisResults"}
                            }
                        }
                    },
                    "404": {"$ref": "#/components/responses/NotFound"}
                }
            }
        },
        "/api/projects/{project_id}/analysis/versions": {
            "get": {
                "tags": ["Analysis"],
                "summary": "List analysis versions",
                "description": "List all analysis versions for a project.",
                "parameters": [
                    {"$ref": "#/components/parameters/ProjectId"},
                    {
                        "name": "status",
                        "in": "query",
                        "schema": {
                            "type": "string",
                            "enum": ["pending", "running", "completed", "failed"]
                        },
                        "description": "Filter by status"
                    },
                    {
                        "name": "limit",
                        "in": "query",
                        "schema": {"type": "integer", "default": 10},
                        "description": "Maximum number to return"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "List of analysis versions",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "versions": {
                                            "type": "array",
                                            "items": {"$ref": "#/components/schemas/AnalysisVersion"}
                                        },
                                        "count": {"type": "integer"}
                                    }
                                }
                            }
                        }
                    },
                    "404": {"$ref": "#/components/responses/NotFound"}
                }
            }
        },
        # ============ Constructs ============
        "/api/projects/{project_id}/constructs": {
            "get": {
                "tags": ["Constructs"],
                "summary": "List constructs for project",
                "parameters": [
                    {"$ref": "#/components/parameters/ProjectId"},
                    {
                        "name": "family",
                        "in": "query",
                        "schema": {"type": "string"},
                        "description": "Filter by family"
                    },
                    {
                        "name": "include_deleted",
                        "in": "query",
                        "schema": {"type": "boolean", "default": False}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "List of constructs",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "constructs": {
                                            "type": "array",
                                            "items": {"$ref": "#/components/schemas/Construct"}
                                        },
                                        "count": {"type": "integer"}
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "post": {
                "tags": ["Constructs"],
                "summary": "Create construct",
                "parameters": [
                    {"$ref": "#/components/parameters/ProjectId"},
                    {
                        "name": "X-Username",
                        "in": "header",
                        "schema": {"type": "string"}
                    }
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ConstructCreate"}
                        }
                    }
                },
                "responses": {
                    "201": {"description": "Construct created"},
                    "400": {"$ref": "#/components/responses/BadRequest"},
                    "409": {"description": "Construct name already exists"}
                }
            }
        },
        "/api/projects/{project_id}/constructs/{construct_id}": {
            "get": {
                "tags": ["Constructs"],
                "summary": "Get construct details",
                "parameters": [
                    {"$ref": "#/components/parameters/ProjectId"},
                    {"$ref": "#/components/parameters/ConstructId"}
                ],
                "responses": {
                    "200": {
                        "description": "Construct details",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Construct"}
                            }
                        }
                    },
                    "404": {"$ref": "#/components/responses/NotFound"}
                }
            },
            "put": {
                "tags": ["Constructs"],
                "summary": "Update construct",
                "parameters": [
                    {"$ref": "#/components/parameters/ProjectId"},
                    {"$ref": "#/components/parameters/ConstructId"},
                    {
                        "name": "X-Username",
                        "in": "header",
                        "schema": {"type": "string"}
                    }
                ],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ConstructUpdate"}
                        }
                    }
                },
                "responses": {
                    "200": {"description": "Construct updated"},
                    "404": {"$ref": "#/components/responses/NotFound"}
                }
            },
            "delete": {
                "tags": ["Constructs"],
                "summary": "Soft-delete construct",
                "parameters": [
                    {"$ref": "#/components/parameters/ProjectId"},
                    {"$ref": "#/components/parameters/ConstructId"},
                    {
                        "name": "X-Username",
                        "in": "header",
                        "schema": {"type": "string"}
                    }
                ],
                "responses": {
                    "200": {"description": "Construct deleted"},
                    "404": {"$ref": "#/components/responses/NotFound"}
                }
            }
        },
        # ============ Layouts ============
        "/api/projects/{project_id}/layouts": {
            "get": {
                "tags": ["Layouts"],
                "summary": "List plate layouts",
                "parameters": [
                    {"$ref": "#/components/parameters/ProjectId"},
                    {
                        "name": "templates_only",
                        "in": "query",
                        "schema": {"type": "boolean", "default": False}
                    },
                    {
                        "name": "include_draft",
                        "in": "query",
                        "schema": {"type": "boolean", "default": True}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "List of layouts",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "layouts": {
                                            "type": "array",
                                            "items": {"$ref": "#/components/schemas/Layout"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "post": {
                "tags": ["Layouts"],
                "summary": "Create plate layout",
                "parameters": [
                    {"$ref": "#/components/parameters/ProjectId"},
                    {
                        "name": "X-Username",
                        "in": "header",
                        "schema": {"type": "string"}
                    }
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/LayoutCreate"}
                        }
                    }
                },
                "responses": {
                    "201": {"description": "Layout created"},
                    "400": {"$ref": "#/components/responses/BadRequest"}
                }
            }
        },
        # ============ Tasks ============
        "/api/tasks/": {
            "get": {
                "tags": ["Tasks"],
                "summary": "List background tasks",
                "parameters": [
                    {
                        "name": "project_id",
                        "in": "query",
                        "schema": {"type": "integer"},
                        "description": "Filter by project"
                    },
                    {
                        "name": "status",
                        "in": "query",
                        "schema": {
                            "type": "string",
                            "enum": ["pending", "running", "completed", "failed"]
                        }
                    },
                    {
                        "name": "active_only",
                        "in": "query",
                        "schema": {"type": "boolean", "default": False},
                        "description": "Only return pending/running tasks"
                    },
                    {
                        "name": "limit",
                        "in": "query",
                        "schema": {"type": "integer", "default": 20}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "List of tasks",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "tasks": {
                                            "type": "array",
                                            "items": {"$ref": "#/components/schemas/TaskProgress"}
                                        },
                                        "count": {"type": "integer"}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/api/tasks/{task_id}": {
            "get": {
                "tags": ["Tasks"],
                "summary": "Get task progress",
                "description": "Poll this endpoint every 2 seconds while task is active.",
                "parameters": [
                    {
                        "name": "task_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Task progress",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/TaskProgress"}
                            }
                        }
                    },
                    "404": {"$ref": "#/components/responses/NotFound"}
                }
            }
        },
        # ============ Calculator ============
        "/api/calculator/dilution": {
            "post": {
                "tags": ["Calculator"],
                "summary": "Calculate dilution series",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["stock_concentration", "target_concentrations", "final_volume"],
                                "properties": {
                                    "stock_concentration": {"type": "number"},
                                    "target_concentrations": {
                                        "type": "array",
                                        "items": {"type": "number"}
                                    },
                                    "final_volume": {"type": "number"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {"description": "Dilution calculations"}
                }
            }
        },
        "/api/calculator/mastermix": {
            "post": {
                "tags": ["Calculator"],
                "summary": "Calculate master mix",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["components", "reactions", "reaction_volume"],
                                "properties": {
                                    "components": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "name": {"type": "string"},
                                                "stock_concentration": {"type": "number"},
                                                "final_concentration": {"type": "number"}
                                            }
                                        }
                                    },
                                    "reactions": {"type": "integer"},
                                    "reaction_volume": {"type": "number"},
                                    "overage_percent": {"type": "number", "default": 20}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {"description": "Master mix calculations"}
                }
            }
        },
        # ============ Smart Planner ============
        "/api/smart-planner/suggest": {
            "post": {
                "tags": ["Smart Planner"],
                "summary": "Get experiment suggestions",
                "description": "AI-powered experiment planning suggestions based on current data.",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["project_id"],
                                "properties": {
                                    "project_id": {"type": "integer"},
                                    "target_precision": {"type": "number", "default": 0.3},
                                    "max_replicates": {"type": "integer", "default": 12}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Experiment suggestions",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ExperimentSuggestions"}
                            }
                        }
                    }
                }
            }
        },
        # ============ Cross-Project ============
        "/api/cross-project/constructs": {
            "get": {
                "tags": ["Cross-Project"],
                "summary": "List shared constructs",
                "description": "Find construct identifiers shared across multiple projects.",
                "parameters": [
                    {
                        "name": "min_projects",
                        "in": "query",
                        "schema": {"type": "integer", "default": 2},
                        "description": "Minimum number of projects"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Shared construct identifiers"
                    }
                }
            }
        },
        "/api/cross-project/compare": {
            "post": {
                "tags": ["Cross-Project"],
                "summary": "Compare construct across projects",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["construct_identifier"],
                                "properties": {
                                    "construct_identifier": {"type": "string"},
                                    "project_ids": {
                                        "type": "array",
                                        "items": {"type": "integer"}
                                    }
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {"description": "Comparison data"}
                }
            }
        }
    },
    "components": {
        "schemas": {
            "ProjectSummary": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"},
                    "slug": {"type": "string"},
                    "description": {"type": "string"},
                    "reporter_system": {"type": "string"},
                    "plate_format": {"type": "string", "enum": ["96", "384"]},
                    "is_draft": {"type": "boolean"},
                    "is_archived": {"type": "boolean"},
                    "created_at": {"type": "string", "format": "date-time"},
                    "updated_at": {"type": "string", "format": "date-time"}
                }
            },
            "Project": {
                "allOf": [
                    {"$ref": "#/components/schemas/ProjectSummary"},
                    {
                        "type": "object",
                        "properties": {
                            "kinetic_model_type": {"type": "string"},
                            "precision_target": {"type": "number"}
                        }
                    }
                ]
            },
            "ProjectCreate": {
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "reporter_system": {"type": "string", "default": "iSpinach"},
                    "plate_format": {"type": "string", "enum": ["96", "384"], "default": "384"},
                    "precision_target": {"type": "number", "default": 0.3}
                }
            },
            "ProjectUpdate": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "reporter_system": {"type": "string"},
                    "precision_target": {"type": "number"}
                }
            },
            "Construct": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"},
                    "identifier": {"type": "string"},
                    "family": {"type": "string"},
                    "anchor_type": {
                        "type": "string",
                        "enum": ["control_negative", "control_positive", "reference", "test"]
                    },
                    "is_control": {"type": "boolean"},
                    "metadata": {"type": "object"},
                    "created_at": {"type": "string", "format": "date-time"}
                }
            },
            "ConstructCreate": {
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {"type": "string"},
                    "identifier": {"type": "string"},
                    "family": {"type": "string"},
                    "anchor_type": {"type": "string"},
                    "is_control": {"type": "boolean", "default": False},
                    "metadata": {"type": "object"}
                }
            },
            "ConstructUpdate": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "identifier": {"type": "string"},
                    "family": {"type": "string"},
                    "anchor_type": {"type": "string"},
                    "is_control": {"type": "boolean"},
                    "metadata": {"type": "object"}
                }
            },
            "Layout": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"},
                    "version": {"type": "integer"},
                    "plate_format": {"type": "string"},
                    "rows": {"type": "integer"},
                    "cols": {"type": "integer"},
                    "is_template": {"type": "boolean"},
                    "is_draft": {"type": "boolean"},
                    "total_wells": {"type": "integer"},
                    "assigned_wells": {"type": "integer"}
                }
            },
            "LayoutCreate": {
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {"type": "string"},
                    "plate_format": {"type": "string", "enum": ["96", "384"]},
                    "is_template": {"type": "boolean", "default": True}
                }
            },
            "TaskProgress": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "task_type": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": ["pending", "running", "completed", "failed"]
                    },
                    "progress": {"type": "number", "minimum": 0, "maximum": 100},
                    "current_step": {"type": "string"},
                    "eta_seconds": {"type": "number"},
                    "error_message": {"type": "string"},
                    "created_at": {"type": "string", "format": "date-time"},
                    "completed_at": {"type": "string", "format": "date-time"}
                }
            },
            "AnalysisVersion": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": ["pending", "running", "completed", "failed"]
                    },
                    "created_at": {"type": "string", "format": "date-time"},
                    "completed_at": {"type": "string", "format": "date-time"}
                }
            },
            "AnalysisResults": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "integer"},
                    "analysis_version": {"$ref": "#/components/schemas/AnalysisVersion"},
                    "posterior_summary": {
                        "type": "object",
                        "properties": {
                            "results": {
                                "type": "array",
                                "items": {"$ref": "#/components/schemas/PosteriorResult"}
                            },
                            "count": {"type": "integer"}
                        }
                    },
                    "fold_changes": {
                        "type": "object",
                        "properties": {
                            "results": {
                                "type": "array",
                                "items": {"$ref": "#/components/schemas/FoldChange"}
                            },
                            "count": {"type": "integer"}
                        }
                    },
                    "convergence": {"$ref": "#/components/schemas/ConvergenceDiagnostics"}
                }
            },
            "PosteriorResult": {
                "type": "object",
                "properties": {
                    "construct_id": {"type": "integer"},
                    "construct_name": {"type": "string"},
                    "parameter": {"type": "string"},
                    "posterior_mean": {"type": "number"},
                    "posterior_std": {"type": "number"},
                    "ci_lower": {"type": "number"},
                    "ci_upper": {"type": "number"},
                    "r_hat": {"type": "number"},
                    "ess_bulk": {"type": "number"},
                    "ess_tail": {"type": "number"}
                }
            },
            "FoldChange": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "test_construct_id": {"type": "integer"},
                    "test_construct_name": {"type": "string"},
                    "control_construct_id": {"type": "integer"},
                    "control_construct_name": {"type": "string"},
                    "log_fold_change": {"type": "number"},
                    "fold_change": {"type": "number"},
                    "ci_lower": {"type": "number"},
                    "ci_upper": {"type": "number"},
                    "standard_error": {"type": "number"},
                    "comparison_type": {"type": "string"},
                    "variance_inflation_factor": {"type": "number"}
                }
            },
            "ConvergenceDiagnostics": {
                "type": "object",
                "properties": {
                    "max_r_hat": {"type": "number"},
                    "min_r_hat": {"type": "number"},
                    "mean_r_hat": {"type": "number"},
                    "min_ess_bulk": {"type": "number"},
                    "mean_ess_bulk": {"type": "number"},
                    "all_converged": {"type": "boolean"},
                    "n_parameters": {"type": "integer"}
                }
            },
            "ExperimentSuggestions": {
                "type": "object",
                "properties": {
                    "suggestions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "construct_id": {"type": "integer"},
                                "construct_name": {"type": "string"},
                                "current_replicates": {"type": "integer"},
                                "suggested_replicates": {"type": "integer"},
                                "current_precision": {"type": "number"},
                                "expected_precision": {"type": "number"},
                                "priority": {"type": "string", "enum": ["high", "medium", "low"]}
                            }
                        }
                    },
                    "total_new_wells": {"type": "integer"},
                    "overall_expected_improvement": {"type": "number"}
                }
            }
        },
        "parameters": {
            "ProjectId": {
                "name": "project_id",
                "in": "path",
                "required": True,
                "schema": {"type": "integer"},
                "description": "Project ID"
            },
            "ConstructId": {
                "name": "construct_id",
                "in": "path",
                "required": True,
                "schema": {"type": "integer"},
                "description": "Construct ID"
            }
        },
        "responses": {
            "NotFound": {
                "description": "Resource not found",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "error": {"type": "string"}
                            }
                        }
                    }
                }
            },
            "BadRequest": {
                "description": "Bad request",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "error": {"type": "string"}
                            }
                        }
                    }
                }
            }
        }
    }
}


SWAGGER_UI_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>IVT Kinetics Analyzer API Documentation</title>
    <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" />
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
        window.onload = function() {
            SwaggerUIBundle({
                url: "/api/openapi.json",
                dom_id: '#swagger-ui',
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIBundle.SwaggerUIStandalonePreset
                ],
                layout: "BaseLayout"
            });
        };
    </script>
</body>
</html>
"""

REDOC_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>IVT Kinetics Analyzer API Documentation</title>
    <link href="https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700" rel="stylesheet">
    <style>body { margin: 0; padding: 0; }</style>
</head>
<body>
    <redoc spec-url='/api/openapi.json'></redoc>
    <script src="https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js"></script>
</body>
</html>
"""


@openapi_bp.route('/openapi.json')
def get_openapi_spec():
    """Return the OpenAPI specification as JSON."""
    return jsonify(OPENAPI_SPEC)


@openapi_bp.route('/docs')
def swagger_ui():
    """Swagger UI documentation interface."""
    return render_template_string(SWAGGER_UI_TEMPLATE)


@openapi_bp.route('/redoc')
def redoc_ui():
    """ReDoc documentation interface."""
    return render_template_string(REDOC_TEMPLATE)


def register_openapi(app):
    """Register the OpenAPI blueprint with the Flask app."""
    app.register_blueprint(openapi_bp)

TraceMatrix frontend build fix
==============================

The original frontend imported InvestigationPage and SourcesPage, but those files were missing from frontend/src/pages. This package adds both pages and keeps the existing routes working.

After extracting this project, open a terminal in the tracematrix folder and run:

  docker compose up --build -d
  docker compose ps

If the build succeeds, open http://localhost:5173.

The pages use the existing backend API. Real provider results still depend on configuration in .env.example/.env. Do not treat fixture/demo results as live evidence.

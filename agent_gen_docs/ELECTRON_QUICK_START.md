# Electron + TypeScript Quick Start

## First Time Setup

1. **Install dependencies**:
   ```bash
   cd frontend
   npm install
   ```

2. **Start development**:
   ```bash
   cd backend
   python -m uvicorn app.main:app --reload
   ```

3. **In another terminal, run the app**:
   ```bash
   cd frontend
   npm run start
   ```

## Common Tasks

### I made changes to TypeScript files

The build happens automatically:
```bash
npm run start  # Rebuilds and launches
```

Or manually:
```bash
npm run build  # Just rebuild without launching
```

### I see an error in the app

Check the browser console:
- Press `Ctrl+Shift+I` (Windows/Linux) or `Cmd+Option+I` (Mac)
- Look for red errors
- Common error: "Error: PUT /api/audio/sources failed: 404" → Backend not running

### I want to type-check without building

```bash
npm run typecheck
```

This finds TypeScript errors without running the full build.

### I want to run tests

```bash
npm test                # Run once
npm run test:watch      # Re-run on changes
```

## Build Pipeline (Simplified)

```
Your TypeScript Source Code
          ↓
     npm run build (Vite)
          ↓
       dist/ folder (JavaScript)
          ↓
     npm run start (Electron)
          ↓
    Desktop App Window
```

**You edit**: `.ts` files in `src/`  
**You run**: `npm run start` in `frontend/`  
**Electron loads**: `dist/index.html` (auto-generated)

## Debugging Checklist

- [ ] Backend running on port 8000? Check `http://127.0.0.1:8000/docs` in a browser
- [ ] `dist/` folder exists? Run `npm run build`
- [ ] App shows blank/error? Check console with `Ctrl+Shift+I`
- [ ] TypeScript syntax errors? Run `npm run typecheck`

See [ELECTRON_TYPESCRIPT_BUILD.md](./ELECTRON_TYPESCRIPT_BUILD.md) for detailed architecture explanation.

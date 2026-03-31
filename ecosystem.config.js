module.exports = {
  apps: [{
    name: 'jarvis-dashboard',
    script: 'uvicorn',
    args: 'main:app --host 0.0.0.0 --port 8003',
    cwd: '/home/ubuntu/projects/jarvis-dashboard',
    interpreter: 'python3',
    watch: false,
    env: { PORT: 8003 }
  }]
}

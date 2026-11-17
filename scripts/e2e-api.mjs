import {spawn} from 'node:child_process'
import path from 'node:path'
const root=path.resolve(import.meta.dirname,'..'),cwd=path.join(root,'apps/api')
const python=path.join(cwd,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python')
const server=spawn(python,['-m','app.test_server'],{cwd,env:process.env,stdio:'inherit'})
process.on('SIGTERM',()=>server.kill());process.on('SIGINT',()=>server.kill())
server.on('exit',code=>process.exit(code||0))

# Port Forwarding WSL → Wi-Fi LAN

> **Configuração:** WSL `172.17.208.219:3000` → Wi-Fi LAN `192.168.0.102`

---

## Step 1 — Criar o Port Forwarding (netsh)

Abre o **PowerShell como Administrador** e corre:

```powershell
netsh interface portproxy add v4tov4 `
  listenaddress=0.0.0.0 `
  listenport=3000 `
  connectaddress=172.17.208.219 `
  connectport=3000
```

> `0.0.0.0` significa que vai escutar em **todas as interfaces**, incluindo o Wi-Fi (`192.168.0.102`).

### Verificar se ficou ativo

```powershell
netsh interface portproxy show all
```

Deves ver algo como:

```
Listen on ipv4:             Connect to ipv4:
Address         Port        Address         Port
--------------- ----------  --------------- ----------
0.0.0.0         3000        172.17.208.219  3000
```

---

## Step 2 — Abrir o Firewall do Windows

O port forwarding sozinho não chega — tens de permitir a porta no firewall:

```powershell
New-NetFirewallRule `
  -DisplayName "WSL Port Forward 3000" `
  -Direction Inbound `
  -Action Allow `
  -Protocol TCP `
  -LocalPort 3000
```

### Testar

De outro dispositivo na mesma rede Wi-Fi, acede a:

```
http://192.168.0.102:3000
```

#!/bin/bash
set -e

echo "=========================================================="
echo "   🚀 PeakPace Server Deployment Script for Proxmox LXC   "
echo "=========================================================="

# 1. Update system & install dependencies
echo "📦 Updating packages and installing prerequisites..."
apt-get update -y
apt-get install -y curl git cifs-utils nfs-common docker.io docker-compose

# 2. Ensure docker service is running
systemctl enable docker
systemctl start docker

# 3. Create TrueNAS Mount directory if not mounted
DATA_DIR="/data"
if [ ! -d "$DATA_DIR" ]; then
    echo "📁 Creating persistent storage directory: $DATA_DIR"
    mkdir -p "$DATA_DIR"
fi

echo "💡 TrueNAS Mount Tip:"
echo "To mount your TrueNAS SMB/NFS share directly into this container:"
echo "1. On Proxmox Host: add 'mp0: /mnt/pve/truenas_share,mp=/data' to /etc/pve/lxc/<CTID>.conf"
echo "   OR inside LXC /etc/fstab: //truenas.local/bigboy/App/data /data cifs username=<user>,password=<pass>,uid=1000,gid=1000 0 0"

# 4. Build and start containers
echo "🐳 Launching PeakPace backend and web dashboard via Docker Compose..."
docker-compose up -d --build

echo ""
echo "=========================================================="
echo "   🎉 PeakPace Running Analytics is LIVE!                 "
echo "   Dashboard:  http://$(hostname -I | awk '{print $1}'):3000"
echo "   Backend API: http://$(hostname -I | awk '{print $1}'):8000"
echo "=========================================================="

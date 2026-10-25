# enable debugging
set -x
PS4='+$(date +"%T.%3N"): '

# load the F5 XC Terraform provider
curl --silent --remote-name-all --output-dir /tmp https://raw.githubusercontent.com/f5education/J1K-26/refs/heads/main/terraform-provider-f5xc_0.9.7_linux_amd64/xc-tf-provider-0{0..9}
cat /tmp/xc-tf-provider-0{0..9} | base64 --decode > /tmp/xc-tf-provider.zip
unzip /tmp/xc-tf-provider.zip -d /tmp
VERSION=$(ls /tmp/terraform-provider-f5xc_v* | sed -E 's/.*_v([0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?).*/\1/' | head -n 1)
chmod +x /tmp/terraform-provider-f5xc_v*
mkdir -p ~/.terraform.d/plugins/registry.terraform.io/F5Networks/f5xc/${VERSION}/linux_amd64/
mv "/tmp/terraform-provider-f5xc_v${VERSION}" ~/.terraform.d/plugins/registry.terraform.io/F5Networks/f5xc/${VERSION}/linux_amd64/

# install the Terraform CLI app
sudo snap install terraform --classic

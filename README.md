# Cloud-Native Self-Service Deployment Platform

Real-time multiplayer word guessing game deployed through a complete DevOps pipeline using Docker, GitHub Actions, Jenkins, Terraform, Kubernetes, AWS EKS, Prometheus and Grafana.

## Architecture

```mermaid
flowchart LR
    Dev[Developer Push] --> GH[GitHub]
    GH --> GHA[GitHub Actions: Tests]
    GH --> Jenkins[Jenkins Pipeline]
    Jenkins --> Docker[Docker Build]
    Docker --> ECR[Amazon ECR]
    Terraform[Terraform IaC] --> VPC[AWS VPC]
    Terraform --> EKS[Amazon EKS]
    ECR --> EKS
    VPC --> EKS
    EKS --> App[Flask Socket.IO Game]
    App --> LB[AWS Load Balancer]
    LB --> User[Public User]
```


## Deployments

### GitHub Actions CI
docs/screenshots/github-actions-success.png

### Jenkins Pipeline
docs/screenshots/jenkins-pipeline-success.png

### Terraform Infrastructure
docs/screenshots/terraform-infrastructure.png

### EKS Nodes
docs/screenshots/eks-nodes-ready.png

### Kubernetes Workload
docs/screenshots/kubernetes-workload.png

### Live Application
docs/screenshots/live-application.png
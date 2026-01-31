# EKS Cost Components and Billing Structure Research

## Overview
Amazon EKS pricing involves multiple cost components that can significantly impact your monthly cloud spending. Understanding each component is crucial for effective FinOps implementation.

## 1. EKS Control Plane Costs

### Standard Control Plane
- **Cost**: $0.10 per hour per cluster
- **Monthly Equivalent**: ~$72 per month (730 hours)
- **What's Included**:
  - Kubernetes API server management
  - etcd data store
  - High availability across multiple AZs (no extra charge)
  - Master node management
  - Control plane security patches and updates

### EKS Provisioned Control Plane (Scaling Tiers)
For larger clusters requiring more control plane capacity:
- **XL Tier**: $1.65 per cluster per hour
- **2XL Tier**: $3.40 per cluster per hour  
- **4XL Tier**: $6.90 per cluster per hour

### Key Points
- Fixed cost regardless of cluster utilization
- Charged even if no workloads are running
- Cannot be optimized through resource tuning

## 2. Worker Node Costs (Compute)

### EC2-Based Worker Nodes
- **Pricing**: Standard EC2 instance pricing applies
- **Options**:
  - **On-Demand**: Pay-per-hour, no commitment
  - **Reserved Instances**: 1-3 year commitments for up to 75% savings
  - **Spot Instances**: Up to 90% discount, but can be interrupted
- **Popular Instance Types for EKS**:
  - t3.medium: ~$0.0416/hour (~$30/month)
  - m5.large: ~$0.096/hour (~$70/month)
  - c5.xlarge: ~$0.192/hour (~$140/month)

### Fargate-Based Worker Nodes
- **vCPU**: $0.04048 per vCPU per hour
- **Memory**: $0.004445 per GB per hour
- **Billing**: Per-second billing with 1-minute minimum
- **Use Case**: Serverless containers, no EC2 management

### EKS Auto Mode
New simplified pricing model with management fees on top of EC2 costs:
- Automatically selects optimal instance types
- Additional management fee varies by instance type
- Example: c6a.2xlarge = $0.306 (EC2) + $0.03672 (management fee)

## 3. Storage Costs

### Amazon EBS (Elastic Block Store)
- **gp3 (General Purpose)**: $0.08 per GB-month
- **gp2 (Legacy)**: $0.10 per GB-month  
- **io2 (High Performance)**: $0.125 per GB-month + IOPS charges
- **Snapshots**: $0.05 per GB-month (incremental)

### Amazon EFS (Elastic File System)
- **Standard**: ~$0.30 per GB-month
- **Infrequent Access (IA)**: ~$0.016 per GB-month
- **Archive**: ~$0.008 per GB-month
- **One Zone**: ~$0.16 per GB-month (reduced durability)

### Amazon FSx
- **FSx for Lustre**: 
  - Scratch: $0.14 per GB-month
  - Persistent SSD: $0.145 per GB-month
  - Persistent HDD: $0.013 per GB-month
- **FSx for ONTAP**: 
  - Standard: $0.30 per hour base
  - Advanced: $1.20 per hour base

### Storage Best Practices
- Right-size EBS volumes to actual usage
- Use lifecycle policies to move data to cheaper tiers
- Implement proper snapshot retention policies
- Consider EFS IA for infrequently accessed data

## 4. Load Balancer Costs

### Application Load Balancer (ALB)
- **Fixed Cost**: $0.0225 per hour (~$16/month)
- **Usage Cost**: $0.008 per LCU-hour
- **LCU (Load Balancer Capacity Unit)** includes:
  - 25 new connections/second
  - 3,000 active connections/minute
  - 1 GB/hour data processed
  - 1,000 rule evaluations/second

### Network Load Balancer (NLB)
- **Fixed Cost**: $0.0252 per hour (~$18/month)
- **Usage Cost**: $0.006 per NLCU-hour
- **NLCU (Network LCU)** includes:
  - 800 new TCP connections/second
  - 100,000 active connections
  - 1 GB/hour data processed
  - 50 new TLS connections/second (for encrypted traffic)

### Load Balancer Best Practices
- Use ALB for HTTP/HTTPS workloads (Layer 7)
- Use NLB for TCP/UDP workloads (Layer 4) or when source IP preservation is needed
- Monitor LCU/NLCU usage to understand scaling costs
- Consider consolidating services behind fewer load balancers where possible

## 5. Data Transfer Charges

### Within Same Availability Zone
- **Cost**: FREE
- **Includes**: Pod-to-pod communication, service discovery

### Cross-Availability Zone (Cross-AZ)
- **Cost**: $0.01 per GB (bidirectional - effectively $0.02 per GB transferred)
- **Common Sources**:
  - Load balancer distributing traffic across AZs
  - Pod communication across AZs
  - Database replication across AZs
  - Kube-proxy forwarding to pods in different AZs

### Internet Egress
- **First 1 GB**: FREE per month
- **Next 9.999 TB**: $0.09 per GB
- **Next 40 TB**: $0.085 per GB
- **Next 100 TB**: $0.07 per GB
- **Over 150 TB**: $0.05 per GB

### Inter-Region Data Transfer
- **Cost**: $0.02 per GB (varies by region pair)
- **Use Cases**: Multi-region deployments, disaster recovery

### Container Registry (ECR) Data Transfer
- **Within Region**: FREE
- **Cross-Region**: Standard data transfer rates apply
- **Internet**: Standard egress rates apply
- **Recommendation**: Use ECR replication to avoid cross-region charges

## 6. Additional Cost Components

### NAT Gateway
- **Cost**: $0.045 per hour + $0.045 per GB processed
- **Use Case**: Internet access for private subnets
- **Optimization**: One NAT Gateway per AZ to avoid cross-AZ charges

### VPC Endpoints
- **Interface Endpoints**: $0.01 per hour + $0.01 per GB processed
- **Gateway Endpoints**: FREE (for S3 and DynamoDB)
- **Benefit**: Avoid internet egress charges for AWS service communication

### Logging and Monitoring
- **CloudWatch Logs**: $0.50 per GB ingested + $0.03 per GB stored
- **CloudWatch Metrics**: $0.30 per metric per month
- **Container Insights**: Additional charges for enhanced monitoring

## 7. Cost Optimization Patterns

### Instance Optimization
- Use Spot instances for fault-tolerant workloads (up to 90% savings)
- Implement cluster autoscaling to match capacity with demand
- Right-size instances based on actual resource utilization
- Use Reserved Instances for predictable workloads

### Network Optimization
- Keep related services in the same AZ when possible
- Use topology-aware routing to minimize cross-AZ traffic
- Implement VPC endpoints for AWS service communication
- Monitor and optimize load balancer traffic patterns

### Storage Optimization
- Use appropriate storage classes for different data types
- Implement automated lifecycle policies
- Regular cleanup of unused volumes and snapshots
- Consider EFS IA for infrequently accessed shared data

## 8. Cost Monitoring Strategies

### AWS Native Tools
- **Cost Explorer**: Analyze spending trends by service/resource
- **Cost and Usage Reports (CUR)**: Detailed billing data for analysis
- **Budget Alerts**: Proactive notifications for cost thresholds
- **Resource Tags**: Enable cost allocation and chargeback

### Third-Party Tools
- **Kubecost**: Kubernetes-native cost monitoring and optimization
- **OpenCost**: Open-source cost monitoring for Kubernetes
- **Cloud optimization platforms**: Holistic cloud cost management

## 9. Real-World Cost Examples

### Small Development Cluster
- 1 Control Plane: $72/month
- 2x t3.medium nodes: $60/month  
- 100GB EBS storage: $8/month
- 1 ALB: $16/month
- **Total**: ~$156/month

### Medium Production Cluster
- 1 Control Plane: $72/month
- 6x m5.large nodes (mix of On-Demand/Spot): $250/month
- 500GB EBS storage: $40/month
- 2 ALBs: $32/month
- Cross-AZ data transfer (10TB): $100/month
- **Total**: ~$494/month

### Large Enterprise Cluster with Fargate
- 1 Control Plane: $72/month
- Fargate (10 tasks, 1 vCPU, 2GB, 100 hours): $49/month
- 1TB EBS storage: $80/month
- 2 ALBs: $32/month
- Cross-AZ data transfer (50TB): $500/month
- **Total**: ~$733/month

## Key Takeaways

1. **Control Plane is Fixed**: $72/month minimum per cluster regardless of usage
2. **Cross-AZ Traffic is Expensive**: Plan network topology carefully
3. **Storage Adds Up**: Monitor and optimize volume usage regularly  
4. **Load Balancers Have Fixed + Variable Costs**: Consolidate where possible
5. **Spot Instances Offer Huge Savings**: Use for fault-tolerant workloads
6. **Data Transfer is Bidirectional**: Cross-AZ charges apply both ways
7. **Monitoring is Essential**: Implement comprehensive cost tracking from day one
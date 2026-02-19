# Docker Bake Configuration
# Usage:
#   docker buildx bake -f docker-bake.hcl                    # All targets
#   docker buildx bake -f docker-bake.hcl api                # API only
#   docker buildx bake -f docker-bake.hcl frontend           # Frontend only
#   docker buildx bake -f docker-bake.hcl --push             # Push to registry
#   docker buildx bake -f docker-bake.hcl --load             # Load to local Docker

variable "REGISTRY" {
  default = "docker.io"
}

variable "IMAGE_NAME" {
  default = "intellifl"
}

variable "TAG" {
  default = "latest"
}

variable "PLATFORMS" {
  default = "linux/amd64,linux/arm64"
}

group "default" {
  targets = ["api", "frontend"]
}

target "api" {
  dockerfile = "Dockerfile"
  context    = "."

  platforms = split(",", PLATFORMS)

  tags = [
    "${REGISTRY}/${IMAGE_NAME}-api:${TAG}",
    "${REGISTRY}/${IMAGE_NAME}-api:latest"
  ]

  provenance = true
  sbom       = true

  cache-from = [
    "type=gha"
  ]
  cache-to = [
    "type=gha,mode=max"
  ]
}

target "frontend" {
  dockerfile = "frontend/Dockerfile"
  context    = "."

  platforms = split(",", PLATFORMS)

  tags = [
    "${REGISTRY}/${IMAGE_NAME}-web:${TAG}",
    "${REGISTRY}/${IMAGE_NAME}-web:latest"
  ]

  provenance = true
  sbom       = true

  cache-from = [
    "type=gha"
  ]
  cache-to = [
    "type=gha,mode=max"
  ]
}

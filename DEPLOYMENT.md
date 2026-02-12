# Production Deployment Checklist

## Pre-Deployment

### 1. Environment Setup
- [ ] Copy `.env.sample` to `.env`
- [ ] Generate a secure `SECRET_KEY`: `openssl rand -hex 32`
- [ ] Set `DATABASE_URL` with production database credentials
- [ ] Set `REDIS_URL` with production Redis instance
- [ ] Set `GITHUB_TOKEN` (personal access token with public_repo scope)
- [ ] Set `GEMINI_API_KEY` for AI features
- [ ] Set `NEXT_PUBLIC_API_URL` to your production domain
- [ ] Set `LOG_LEVEL=info` for production (not debug)
- [ ] Set `NODE_ENV=production`

### 2. Security Review
- [ ] Change default database credentials
- [ ] Use strong SECRET_KEY (never commit to git)
- [ ] Enable HTTPS on frontend proxy
- [ ] Setup CORS properly for production domain
- [ ] Review API rate limits
- [ ] Setup firewall rules
- [ ] Use environment-specific secrets management (AWS Secrets, Vault, etc.)

### 3. Infrastructure
- [ ] Setup PostgreSQL database (14+)
- [ ] Setup Redis instance (6+)
- [ ] Configure database backups
- [ ] Setup monitoring and alerting
- [ ] Configure log aggregation
- [ ] Setup SSL/TLS certificates

### 4. Code Changes
- [ ] Remove test/dummy data
- [ ] Verify no hardcoded credentials
- [ ] Check error handling and logging
- [ ] Review database migrations
- [ ] Ensure all dependencies are in requirements.txt and package.json

### 5. Testing Before Deployment
```bash
# Run all tests
make test

# Run with coverage
make test-coverage

# Check code quality
make lint

# Format code
make format

# Build Docker images
make build
```

## Deployment Steps

### Option 1: Docker Compose (Recommended)

```bash
# 1. Prepare environment
cp .env.sample .env
# Edit .env with production values

# 2. Build images
docker-compose build --no-cache

# 3. Run deployment script
chmod +x deploy.sh
./deploy.sh

# 4. Monitor services
docker-compose logs -f
```

### Option 2: Manual Deployment

```bash
# Stop old services
docker-compose down

# Start new services
docker-compose up -d

# Wait for services
sleep 15

# Verify
make health
```

## Post-Deployment

### 1. Verification
- [ ] Access frontend at your domain
- [ ] Login with test account
- [ ] Verify API docs accessible
- [ ] Test analysis functionality
- [ ] Check logs for errors
- [ ] Verify database is persisting data

### 2. Monitoring
- [ ] Setup application monitoring
- [ ] Setup error tracking (Sentry, etc.)
- [ ] Setup performance monitoring
- [ ] Configure alerts for failures
- [ ] Setup automated backups

### 3. Database
- [ ] Verify backups are working
- [ ] Test restore procedure
- [ ] Monitor database size
- [ ] Setup maintenance jobs

### 4. SSL/TLS
- [ ] Verify HTTPS is working
- [ ] Setup certificate renewal
- [ ] Test SSL configuration
- [ ] Update API URLs to HTTPS

### 5. Updates & Maintenance
```bash
# Pull latest code
git pull origin main

# Rebuild images
make build

# Restart services with zero downtime
docker-compose up -d --no-recreate
```

## Scaling Considerations

### Horizontal Scaling
- Use load balancer (nginx, HAProxy, AWS LB)
- Run multiple backend instances
- Increase Celery worker concurrency: `CELERY_CONCURRENCY=8`

### Performance Tuning
- Enable Redis persistence for Celery
- Optimize PostgreSQL settings
- Configure connection pooling
- Increase memory limits if needed

### Disaster Recovery
- Automated database backups
- Multi-region setup
- Failover procedures
- Regular DR testing

## Troubleshooting

### Services won't start
```bash
# Check Docker daemon
sudo systemctl status docker

# View detailed logs
docker-compose logs

# Rebuild images
docker-compose down -v
docker-compose build --no-cache
docker-compose up
```

### Database connection issues
```bash
# Verify connection string in .env
# Test connection:
psql postgresql://user:password@host:5432/dbname

# Check PostgreSQL logs
docker-compose logs db
```

### Celery not processing tasks
```bash
# Check Redis connection
redis-cli ping

# View Celery logs
docker-compose logs celery_worker

# Restart worker
docker-compose restart celery_worker
```

### Frontend not connecting to API
```bash
# Verify NEXT_PUBLIC_API_URL in .env
# Check browser console for errors
# Verify CORS settings in FastAPI
# Test API directly: curl http://localhost:8000/docs
```

## Rollback Procedure

```bash
# Stop current deployment
docker-compose down

# Checkout previous version
git checkout <previous-commit>

# Rebuild and redeploy
make build
docker-compose up -d

# Verify
make health
```

## Monitoring Dashboard

Setup monitoring for:
- CPU and memory usage
- Database connections
- Redis memory usage
- API response times
- Failed tasks
- Error rates
- User sessions

## Security Hardening

1. **Database**
   - Use strong passwords
   - Restrict network access
   - Enable SSL connections
   - Regular security updates

2. **Redis**
   - Require authentication
   - Use TLS connections
   - Restrict network access
   - Regular updates

3. **API Security**
   - Rate limiting enabled
   - Input validation
   - HTTPS only
   - CORS configured
   - API keys rotated regularly

4. **Frontend**
   - Content Security Policy headers
   - HTTPS only
   - Secure cookies
   - Regular updates

## Post-Incident

- [ ] Document what happened
- [ ] Review monitoring alerts
- [ ] Implement preventive measures
- [ ] Update runbooks
- [ ] Team debrief

---

For more details, see [README.md](README.md) and [Makefile](Makefile)

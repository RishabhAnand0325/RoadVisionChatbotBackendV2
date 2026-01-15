# Memory Crash Fix - Deployment Guide

## Problem
The tender analysis script was being killed by the system with "Killed" error due to excessive memory usage during PDF processing.

## Solution
We've implemented comprehensive memory management to prevent system crashes.

## Quick Fix Steps

### 1. Update Dependencies
```bash
pip install psutil
```

### 2. Use the Memory-Optimized Script
```bash
# Instead of running the original script directly
python3 scripts/analyze_tender_optimized.py 51706378
```

### 3. Alternative: Update Original Script
The main script `app/modules/analyze/scripts/analyze_tender.py` has been updated with memory management. Just ensure psutil is installed:
```bash
pip install psutil
python3 -m app.modules.analyze.scripts.analyze_tender 51706378
```

## What Was Changed

### 1. Memory Monitoring
- Added psutil for real-time memory usage tracking
- Set memory thresholds to prevent excessive usage
- Monitor process memory before and after operations

### 2. File Size Limits
- Skip files larger than 50MB to prevent memory exhaustion
- Added file size checks before processing
- Graceful fallback for oversized documents

### 3. Resource-Aware Processing
- Use `process_pdf()` method instead of direct `extract_text_from_pdf()`
- The `process_pdf()` method includes built-in memory management
- Better chunking strategy to handle large documents

### 4. Environment Optimization
- Set `TOKENIZERS_PARALLELISM=false` to reduce memory usage
- Disable GPU usage to avoid CUDA memory issues
- Force garbage collection between operations

## For EC2 Deployment

### Recommended EC2 Instance Types
- **Minimum**: t3.medium (4GB RAM)
- **Recommended**: t3.large (8GB RAM)
- **For large tenders**: t3.xlarge (16GB RAM)

### EC2 Setup Commands
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required system packages
sudo apt install -y python3-pip python3-venv tesseract-ocr

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
pip install psutil

# Set memory optimization environment variables
export TOKENIZERS_PARALLELISM=false
export TF_FORCE_GPU_ALLOW_GROWTH=true
export CUDA_VISIBLE_DEVICES=""

# Run the optimized script
python3 scripts/analyze_tender_optimized.py 51706378
```

### Monitor Memory Usage
```bash
# Check memory before running
free -h

# Monitor during execution (in another terminal)
watch -n 1 'free -h && ps aux | grep python'

# Check memory after completion
free -h
```

## Troubleshooting

### If Still Getting "Killed" Error
1. **Check available memory**: `free -h`
2. **Reduce file size limit**: Edit `MAX_FILE_SIZE_MB` in the script to 25MB or 10MB
3. **Use smaller instance**: Process files one at a time with delays
4. **Add swap space**: 
   ```bash
   sudo fallocate -l 2G /swapfile
   sudo chmod 600 /swapfile
   sudo mkswap /swapfile
   sudo swapon /swapfile
   ```

### If psutil Import Error
```bash
# Activate virtual environment first
source venv/bin/activate
pip install psutil

# Or install system-wide
sudo pip3 install psutil
```

### If PDF Processing Still Fails
1. **Check PDF file size**: `ls -lh /path/to/pdf/files/`
2. **Process smaller batches**: Split tender processing into smaller chunks
3. **Use text-only processing**: Skip OCR for text-based PDFs

## Environment Variables for Memory Optimization

Add these to your `.bashrc` or set before running:

```bash
export TOKENIZERS_PARALLELISM=false
export TF_FORCE_GPU_ALLOW_GROWTH=true
export TF_CPP_MIN_LOG_LEVEL=3
export PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:128
export CUDA_VISIBLE_DEVICES=""
export OMP_NUM_THREADS=1
```

## Testing the Fix

### Quick Test
```bash
# Test with memory monitoring
python3 scripts/analyze_tender_optimized.py 51706378

# Expected output should show:
# 💾 Memory: X.XGB available / X.XGB total
# 🔒 Set memory limit to 2.0GB
# 🏁 Starting analysis with XXMB initial memory
# ✅ Analysis completed successfully!
```

### Memory Usage Validation
The script should now:
1. Check available memory before starting
2. Set memory limits to prevent system kill
3. Skip oversized files (>50MB)
4. Monitor memory usage throughout processing
5. Complete without "Killed" errors

## Support
If issues persist:
1. Share memory usage output: `free -h`
2. Share instance specifications: `cat /proc/meminfo`
3. Check logs for specific error messages
4. Try the optimized script first before debugging further
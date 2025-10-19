- Assumes pwd is the root directory and executables are set up.
## To run custom tests:
- add your sample json files named as ```factory_*.in.json```, ```factory_*.out.json```,  ```belts_*.in.json``` , ```belts_*.out.json```

```python3 run_samples.py "python3 factory/main.py" "python3 belts/main.py"```

## To run pytest test:
```FACTORY_CMD="python3 factory/main.py" BELTS_CMD="python3 belts/main.py" pytest -q tests/```

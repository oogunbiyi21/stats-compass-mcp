# Known issues

Tickets recorded but not yet fixed. Each says what is wrong, why, and the fix.

## run_timeseries_workflow never slices large datasets

**Found 9 October 2026, while fixing the re-scan of 0.3.32. Not security; open.**

**What the tool promises.** `run_timeseries_workflow`'s docstring says datasets
over 500 rows are cut to the most recent 500 before the ARIMA fit, to keep it
fast.

**What happens.** The cut is never used. In `stats_compass_mcp/tools/workflows.py`
the slice is stored with its arguments swapped:

```python
session.state.set_dataframe(temp_name, sliced)
```

`DataFrameState.set_dataframe` takes `(df, name, operation, set_active=True)`.
Passed a name where the frame belongs and no `operation`, it raises
`TypeError: ... missing 1 required positional argument: 'operation'` (checked
on core 0.1.40).

The surrounding `try` ends in `except Exception: pass`, so the error is
swallowed. `dataframe_name` is never switched to the sliced frame, and the
workflow fits ARIMA on the whole dataset. On a large frame that is the slow fit
the cut was meant to avoid, and the log never says the cut was skipped.

**Fix.**
- Store the frame with keyword arguments:
  `session.state.set_dataframe(sliced, name=temp_name, operation="timeseries_slice", set_active=False)`.
- Narrow the `except` so a failure is logged as a warning, not silenced.
- Add a test with a 600-row series that asserts the fit used 500 rows.
- Check the existing cleanup of `temp_name` still removes the sliced frame.

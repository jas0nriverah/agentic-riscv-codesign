(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x92 (bvmul x (_ bv32 32))))
(let ((?x90 (bvshl x (_ bv5 32))))
(and (distinct ?x90 ?x92) true))))
(check-sat)

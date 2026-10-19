(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x50 (bvmul x (_ bv1 32))))
(let ((?x49 (bvshl x (_ bv0 32))))
(and (distinct ?x49 ?x50) true))))
(check-sat)

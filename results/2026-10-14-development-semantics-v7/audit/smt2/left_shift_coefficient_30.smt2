(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x315 (bvmul x (_ bv1073741824 32))))
(let ((?x313 (bvshl x (_ bv30 32))))
(and (distinct ?x313 ?x315) true))))
(check-sat)

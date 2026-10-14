(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x497 (bvsub (_ bv0 32) (bvshl independent_opaque_0 (bvand (_ bv2 32) (_ bv31 32))))))
(let ((?x493 (bvand (_ bv2 32) (_ bv31 32))))
(let ((?x305 (bvshl (bvsub (_ bv0 32) independent_opaque_0) ?x493)))
(and (distinct ?x305 ?x497) true)))))
(check-sat)

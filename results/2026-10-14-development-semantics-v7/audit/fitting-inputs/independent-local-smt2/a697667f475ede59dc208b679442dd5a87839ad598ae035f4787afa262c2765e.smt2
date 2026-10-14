(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x334 (bvadd independent_opaque_0 (bvadd (bvshl independent_opaque_1 (bvand (_ bv2 32) (_ bv31 32))) (_ bv2304 32)))))
(let ((?x15 (bvadd independent_opaque_0 (bvshl (bvadd independent_opaque_1 (_ bv576 32)) (bvand (_ bv2 32) (_ bv31 32))))))
(and (distinct ?x15 ?x334) true))))
(check-sat)

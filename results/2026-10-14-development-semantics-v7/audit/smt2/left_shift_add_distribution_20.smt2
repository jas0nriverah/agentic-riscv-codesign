(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x227 (bvshl y (_ bv20 32))))
(let ((?x223 (bvshl x (_ bv20 32))))
(let ((?x228 (bvadd ?x223 ?x227)))
(let ((?x19 (bvadd x y)))
(let ((?x226 (bvshl ?x19 (_ bv20 32))))
(and (distinct ?x226 ?x228) true)))))))
(check-sat)
